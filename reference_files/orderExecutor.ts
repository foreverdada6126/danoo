import * as ccxt from 'ccxt';

export type ExecutionMode = 'paper' | 'testnet' | 'live';

export interface OrderRequest {
    symbol: string;
    side: 'BUY' | 'SELL';
    type: 'MARKET' | 'LIMIT' | 'STOP_MARKET';
    quantity: number;
    price?: number;          // For LIMIT orders
    stopPrice?: number;      // For STOP_MARKET orders
    reduceOnly?: boolean;    // Close position only
    timeInForce?: 'GTC' | 'IOC' | 'FOK';
}

export interface OrderResult {
    orderId: string;
    symbol: string;
    side: 'BUY' | 'SELL';
    type: string;
    quantity: number;
    price: number;           // Fill price
    status: 'FILLED' | 'REJECTED' | 'CANCELED' | 'PENDING';
    timestamp: number;
    mode: ExecutionMode;
    commission: number;
    error?: string;
}

export interface Position {
    symbol: string;
    side: 'LONG' | 'SHORT';
    entryPrice: number;
    quantity: number;
    unrealizedPnl: number;
    entryTime: number;
    stopLoss?: number;
    takeProfit?: number;
    strategy: string;
}

export interface APICredentials {
    apiKey: string;
    apiSecret: string;
}

export class OrderExecutor {
    private mode: ExecutionMode;
    private credentials: APICredentials | null = null;
    private exchange: ccxt.binance | null = null;
    private paperBalance: number;
    private paperPositions: Map<string, Position> = new Map();
    private orderHistory: OrderResult[] = [];
    private commission: number = 0.0004; // 0.04%

    // Cache for real trading state
    private lastRealBalance: number = 0;
    private realPositions: Map<string, Position> = new Map();

    constructor(mode: ExecutionMode = 'paper', initialBalance: number = 10000) {
        this.mode = mode;
        this.paperBalance = initialBalance;
        this.lastRealBalance = initialBalance;
        this.initExchange();
        console.log(`[OrderExecutor] Initialized in ${mode.toUpperCase()} mode`);
    }

    private initExchange() {
        if (this.mode === 'paper') return;

        this.exchange = new ccxt.binance({
            apiKey: this.credentials?.apiKey,
            secret: this.credentials?.apiSecret,
            options: {
                defaultType: 'future',
            }
        });

        if (this.mode === 'testnet') {
            this.exchange.setSandboxMode(true);
        }
    }

    setCredentials(creds: APICredentials): void {
        this.credentials = creds;
        this.initExchange();
        console.log(`[OrderExecutor] API credentials set for ${this.mode} mode`);
    }

    async setLeverage(symbol: string, leverage: number): Promise<void> {
        if (this.mode === 'paper' || !this.exchange) return;
        try {
            const ccxtSymbol = this.toCcxtSymbol(symbol);
            await this.exchange.setLeverage(leverage, ccxtSymbol);
            console.log(`[OrderExecutor] Leverage set to ${leverage}x for ${symbol}`);
        } catch (error: any) {
            console.error(`[OrderExecutor] Failed to set leverage:`, error.message);
        }
    }

    private toCcxtSymbol(symbol: string): string {
        if (symbol.includes(':') || symbol.includes('/')) return symbol;
        if (symbol.endsWith('USDT')) {
            return `${symbol.replace('USDT', '')}/USDT:USDT`;
        }
        return symbol;
    }

    getMode(): ExecutionMode {
        return this.mode;
    }

    setMode(mode: ExecutionMode): void {
        this.mode = mode;
        this.initExchange();
        console.log(`[OrderExecutor] Switched to ${mode.toUpperCase()} mode`);
    }

    // ─── Order Execution ──────────────────────────────────

    async placeOrder(request: OrderRequest, currentPrice: number): Promise<OrderResult> {
        switch (this.mode) {
            case 'paper':
                return this.executePaper(request, currentPrice);
            case 'testnet':
            case 'live':
                return this.executeReal(request);
            default:
                throw new Error(`Unknown execution mode: ${this.mode}`);
        }
    }

    async closePosition(symbol: string, currentPrice: number): Promise<OrderResult | null> {
        const pos = await this.getPosition(symbol);
        if (!pos || Math.abs(pos.quantity) < 0.0001) return null;

        const closeSide = pos.side === 'LONG' ? 'SELL' : 'BUY';
        const result = await this.placeOrder({
            symbol,
            side: closeSide,
            type: 'MARKET',
            quantity: Math.abs(pos.quantity),
            reduceOnly: true,
        }, currentPrice);

        if (this.mode === 'paper' && result.status === 'FILLED') {
            this.paperPositions.delete(symbol);
        }

        return result;
    }

    // ─── Paper Trading (Simulated) ─────────────────────────

    private executePaper(request: OrderRequest, currentPrice: number): OrderResult {
        const fillPrice = currentPrice;
        const commissionAmount = fillPrice * request.quantity * this.commission;
        const orderId = `PAPER_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

        if (request.reduceOnly) {
            const pos = this.paperPositions.get(request.symbol);
            if (pos) {
                const pnl = pos.side === 'LONG'
                    ? (fillPrice - pos.entryPrice) * pos.quantity
                    : (pos.entryPrice - fillPrice) * pos.quantity;
                this.paperBalance += pnl - commissionAmount;
            }
        } else {
            this.paperBalance -= commissionAmount;
            const side = request.side === 'BUY' ? 'LONG' : 'SHORT';
            this.paperPositions.set(request.symbol, {
                symbol: request.symbol,
                side,
                entryPrice: fillPrice,
                quantity: request.quantity,
                unrealizedPnl: 0,
                entryTime: Date.now(),
                strategy: 'unknown',
            });
        }

        const result: OrderResult = {
            orderId,
            symbol: request.symbol,
            side: request.side,
            type: request.type,
            quantity: request.quantity,
            price: fillPrice,
            status: 'FILLED',
            timestamp: Date.now(),
            mode: 'paper',
            commission: commissionAmount,
        };

        this.orderHistory.push(result);
        return result;
    }

    // ─── Real Trading (CCXT) ───────────────────────────────

    private async executeReal(request: OrderRequest): Promise<OrderResult> {
        if (!this.exchange || !this.credentials) {
            return this.errorResult(request, 'No API credentials configured.');
        }

        try {
            const ccxtSymbol = this.toCcxtSymbol(request.symbol);
            const side = request.side.toLowerCase() as 'buy' | 'sell';
            const type = request.type.toLowerCase();

            const params: any = {};
            if (request.reduceOnly) params.reduceOnly = true;
            if (request.stopPrice) params.stopPrice = request.stopPrice;

            const order = await this.exchange.createOrder(
                ccxtSymbol,
                type,
                side,
                request.quantity,
                request.price,
                params
            );

            const result: OrderResult = {
                orderId: order.id,
                symbol: request.symbol,
                side: request.side,
                type: request.type,
                quantity: (order.filled !== undefined ? order.filled : (order.amount !== undefined ? order.amount : request.quantity)),
                price: (order.average !== undefined ? order.average : (order.price !== undefined ? order.price : 0)),
                status: order.status === 'closed' || order.status === 'filled' ? 'FILLED' : 'PENDING',
                timestamp: order.timestamp || Date.now(),
                mode: this.mode,
                commission: (order.fee && typeof order.fee.cost === 'number') ? order.fee.cost : 0,
            };

            this.orderHistory.push(result);
            return result;

        } catch (error: any) {
            console.error(`[OrderExecutor] CCXT Error:`, error.message);
            return this.errorResult(request, `CCXT Error: ${error.message}`);
        }
    }

    private errorResult(request: OrderRequest, error: string): OrderResult {
        return {
            orderId: 'NONE',
            symbol: request.symbol,
            side: request.side,
            type: request.type,
            quantity: request.quantity,
            price: 0,
            status: 'REJECTED',
            timestamp: Date.now(),
            mode: this.mode,
            commission: 0,
            error,
        };
    }

    // ─── State Queries ─────────────────────────────────────

    async fetchState(): Promise<void> {
        if (this.mode === 'paper' || !this.exchange) return;

        try {
            // Fetch Balance
            const balance: any = await this.exchange.fetchBalance();
            this.lastRealBalance = balance.total.USDT || balance.USDT.total || this.lastRealBalance;

            // Fetch Positions
            const positions = await this.exchange.fetchPositions();
            this.realPositions.clear();
            for (const p of positions) {
                if (p.contracts && p.contracts > 0) {
                    const symbol = p.symbol.split('/')[0] + p.symbol.split('/')[1].split(':')[0]; // ETHUSDT
                    this.realPositions.set(symbol, {
                        symbol,
                        side: p.side === 'long' ? 'LONG' : 'SHORT',
                        entryPrice: p.entryPrice || 0,
                        quantity: p.contracts || 0,
                        unrealizedPnl: p.unrealizedPnl || 0,
                        entryTime: p.timestamp || Date.now(),
                        strategy: 'live',
                    });
                }
            }
        } catch (error: any) {
            console.error(`[OrderExecutor] Failed to fetch state:`, error.message);
        }
    }

    getBalance(): number {
        return this.mode === 'paper' ? this.paperBalance : this.lastRealBalance;
    }

    async getPosition(symbol: string): Promise<Position | undefined> {
        if (this.mode === 'paper') return this.paperPositions.get(symbol);

        await this.fetchState();
        return this.realPositions.get(symbol);
    }

    getAllPositions(): Position[] {
        return this.mode === 'paper'
            ? Array.from(this.paperPositions.values())
            : Array.from(this.realPositions.values());
    }

    getOrderHistory(): OrderResult[] {
        return [...this.orderHistory];
    }

    updatePositionPnL(prices: Record<string, number>): void {
        const positions = this.mode === 'paper' ? this.paperPositions : this.realPositions;
        for (const [symbol, pos] of positions) {
            const currentPrice = prices[symbol];
            if (currentPrice) {
                pos.unrealizedPnl = pos.side === 'LONG'
                    ? (currentPrice - pos.entryPrice) * pos.quantity
                    : (pos.entryPrice - currentPrice) * pos.quantity;
            }
        }
    }

    getEquity(): number {
        let unrealized = 0;
        const positions = this.mode === 'paper' ? this.paperPositions : this.realPositions;
        for (const pos of positions.values()) {
            unrealized += pos.unrealizedPnl;
        }
        return this.getBalance() + unrealized;
    }

    getStats(): { totalTrades: number; wins: number; losses: number; totalPnl: number; winRate: number } {
        const closes = this.orderHistory.filter(o => o.status === 'FILLED');
        const roundTrips = Math.floor(closes.length / 2);
        let wins = 0, losses = 0, totalPnl = 0;

        for (let i = 1; i < closes.length; i += 2) {
            const open = closes[i - 1];
            const close = closes[i];
            const pnl = open.side === 'BUY'
                ? (close.price - open.price) * open.quantity
                : (open.price - close.price) * open.quantity;
            totalPnl += pnl;
            if (pnl > 0) wins++;
            else losses++;
        }

        return {
            totalTrades: roundTrips,
            wins,
            losses,
            totalPnl,
            winRate: roundTrips > 0 ? (wins / roundTrips) * 100 : 0,
        };
    }
}
