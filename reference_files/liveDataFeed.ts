/**
 * Live Data Feed — Binance WebSocket Kline Stream
 * 
 * Connects to Binance Futures WebSocket for real-time candle data.
 * Maintains a rolling buffer of closed candles for indicator calculation.
 * Supports any symbol and timeframe.
 */

import WebSocket from 'ws';
import { Candle } from './indicators';

export interface DataFeedConfig {
    symbol: string;
    timeframe: string;
    bufferSize: number;       // How many candles to keep in memory (for indicators)
    useFutures: boolean;      // Futures vs Spot
    useTestnet: boolean;      // Testnet vs Production
}

export interface LiveCandle extends Candle {
    isClosed: boolean;
    symbol: string;
    timeframe: string;
}

type CandleCallback = (candle: LiveCandle, buffer: Candle[]) => void;
type StatusCallback = (status: 'connected' | 'disconnected' | 'reconnecting' | 'error', message?: string) => void;

const WS_ENDPOINTS = {
    futures_live: 'wss://fstream.binance.com/ws',
    futures_testnet: 'wss://stream.binancefuture.com/ws',
    spot_live: 'wss://stream.binance.com:9443/ws',
};

const REST_ENDPOINTS = {
    futures_live: 'https://fapi.binance.com',
    futures_testnet: 'https://testnet.binancefuture.com',
    spot_live: 'https://api.binance.com',
};

export class LiveDataFeed {
    private config: DataFeedConfig;
    private ws: WebSocket | null = null;
    private candleBuffer: Candle[] = [];
    private currentCandle: LiveCandle | null = null;
    private onCandle: CandleCallback | null = null;
    private onStatus: StatusCallback | null = null;
    private reconnectTimer: NodeJS.Timeout | null = null;
    private heartbeatTimer: NodeJS.Timeout | null = null;
    private lastPong: number = 0;
    private isRunning: boolean = false;

    constructor(config: Partial<DataFeedConfig> = {}) {
        this.config = {
            symbol: 'ETHUSDT',
            timeframe: '15m',
            bufferSize: 500,
            useFutures: true,
            useTestnet: false,
            ...config
        };
    }

    /**
     * Pre-load historical candles to fill buffer before going live
     */
    async warmup(): Promise<void> {
        const endpoint = this.config.useFutures
            ? (this.config.useTestnet ? REST_ENDPOINTS.futures_testnet : REST_ENDPOINTS.futures_live)
            : REST_ENDPOINTS.spot_live;

        const path = this.config.useFutures ? '/fapi/v1/klines' : '/api/v3/klines';
        const url = `${endpoint}${path}?symbol=${this.config.symbol}&interval=${this.config.timeframe}&limit=${this.config.bufferSize}`;

        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error(`Warmup failed: ${response.statusText}`);
            const data: any[] = await response.json() as any[];

            this.candleBuffer = data.map((k: any) => ({
                open_time: k[0],
                open: parseFloat(k[1]),
                high: parseFloat(k[2]),
                low: parseFloat(k[3]),
                close: parseFloat(k[4]),
                volume: parseFloat(k[5]),
                close_time: k[6],
            }));

            // Remove the last candle if it's still open (incomplete)
            if (this.candleBuffer.length > 0) {
                const lastCandle = this.candleBuffer[this.candleBuffer.length - 1];
                if (lastCandle.close_time > Date.now()) {
                    this.candleBuffer.pop();
                }
            }

            console.log(`[DataFeed] Warmed up with ${this.candleBuffer.length} historical candles for ${this.config.symbol} ${this.config.timeframe}`);
        } catch (error) {
            console.error('[DataFeed] Warmup error:', error);
            throw error;
        }
    }

    /**
     * Start streaming live candles
     */
    start(onCandle: CandleCallback, onStatus?: StatusCallback): void {
        this.onCandle = onCandle;
        this.onStatus = onStatus || null;
        this.isRunning = true;
        this.connect();
    }

    /**
     * Stop the data feed
     */
    stop(): void {
        this.isRunning = false;
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
        this.emitStatus('disconnected', 'Feed stopped');
    }

    /**
     * Get the current candle buffer (for indicator calculations)
     */
    getBuffer(): Candle[] {
        return [...this.candleBuffer];
    }

    /**
     * Get the latest closing price
     */
    getLastPrice(): number {
        if (this.currentCandle) return this.currentCandle.close;
        if (this.candleBuffer.length > 0) return this.candleBuffer[this.candleBuffer.length - 1].close;
        return 0;
    }

    // ─── Internal ──────────────────────────────────────────

    private connect(): void {
        const wsBase = this.config.useFutures
            ? (this.config.useTestnet ? WS_ENDPOINTS.futures_testnet : WS_ENDPOINTS.futures_live)
            : WS_ENDPOINTS.spot_live;

        const stream = `${this.config.symbol.toLowerCase()}@kline_${this.config.timeframe}`;
        const url = `${wsBase}/${stream}`;

        console.log(`[DataFeed] Connecting to ${url}...`);
        this.emitStatus('reconnecting', `Connecting to ${this.config.symbol}...`);

        this.ws = new WebSocket(url);

        this.ws.on('open', () => {
            console.log(`[DataFeed] ✅ Connected: ${this.config.symbol} ${this.config.timeframe}`);
            this.emitStatus('connected', `Live on ${this.config.symbol}`);
            this.lastPong = Date.now();
            this.startHeartbeat();
        });

        this.ws.on('message', (raw: WebSocket.Data) => {
            try {
                const data = JSON.parse(raw.toString());
                if (data.e === 'kline') {
                    this.handleKline(data.k);
                }
            } catch (e) {
                // Ignore parse errors (pong frames etc)
            }
        });

        this.ws.on('pong', () => {
            this.lastPong = Date.now();
        });

        this.ws.on('error', (err) => {
            console.error('[DataFeed] WebSocket error:', err.message);
            this.emitStatus('error', err.message);
        });

        this.ws.on('close', () => {
            console.log('[DataFeed] WebSocket closed');
            this.emitStatus('disconnected');
            if (this.isRunning) {
                this.scheduleReconnect();
            }
        });
    }

    private handleKline(k: any): void {
        const candle: LiveCandle = {
            open_time: k.t,
            open: parseFloat(k.o),
            high: parseFloat(k.h),
            low: parseFloat(k.l),
            close: parseFloat(k.c),
            volume: parseFloat(k.v),
            close_time: k.T,
            isClosed: k.x,
            symbol: k.s,
            timeframe: k.i,
        };

        this.currentCandle = candle;

        // When a candle closes, add it to the buffer and notify
        if (candle.isClosed) {
            const closedCandle: Candle = {
                open_time: candle.open_time,
                open: candle.open,
                high: candle.high,
                low: candle.low,
                close: candle.close,
                volume: candle.volume,
                close_time: candle.close_time,
            };

            this.candleBuffer.push(closedCandle);

            // Trim buffer to configured size
            if (this.candleBuffer.length > this.config.bufferSize) {
                this.candleBuffer = this.candleBuffer.slice(-this.config.bufferSize);
            }

            if (this.onCandle) {
                this.onCandle(candle, this.candleBuffer);
            }
        }
    }

    private startHeartbeat(): void {
        if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
        this.heartbeatTimer = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                // If no pong in 30s, reconnect
                if (Date.now() - this.lastPong > 30000) {
                    console.log('[DataFeed] Heartbeat timeout, reconnecting...');
                    this.ws.close();
                    return;
                }
                this.ws.ping();
            }
        }, 10000);
    }

    private scheduleReconnect(): void {
        if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
        console.log('[DataFeed] Reconnecting in 5s...');
        this.reconnectTimer = setTimeout(() => {
            if (this.isRunning) this.connect();
        }, 5000);
    }

    private emitStatus(status: 'connected' | 'disconnected' | 'reconnecting' | 'error', message?: string): void {
        if (this.onStatus) this.onStatus(status, message);
    }
}
