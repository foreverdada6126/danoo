import { Candle, TechnicalIndicators } from './indicators';
import { RegimeClassifier, MarketRegime } from './regime';
import { RiskManager, RISK_PRESETS, RiskConfig } from './riskManagement';

export interface Trade {
  entryTime: number;
  entryPrice: number;
  exitTime: number;
  exitPrice: number;
  side: 'LONG' | 'SHORT';
  pnl: number;
  pnlPercent: number;
  regime: MarketRegime;
  strategy: string;
  leverage: number;
  positionSize: number;
  riskAmount: number;
}

export interface BacktestResults {
  strategy: string;
  regime: MarketRegime | 'ALL';
  leverage: number;
  totalPnL: number;
  totalPnLPercent: number;
  winRate: number;
  trades: Trade[];
  tradeCount: number;
  winCount: number;
  lossCount: number;
  maxDrawdown: number;
  sharpeRatio: number;
  profitFactor: number;
  avgWin: number;
  avgLoss: number;
  largestWin: number;
  largestLoss: number;
}

export interface StrategyParams {
  // VolatilityExpansion
  compressionPercentile?: number;
  volumeSpikeMultiple?: number;
  tpRR?: number;
  atrStopMult?: number;

  // MeanReversion
  rsiEntry?: number;
  maxHoldBars?: number;
  atrStopMultMR?: number;

  // Momentum
  adxThreshold?: number;
  atrTrailMult?: number;
  pullbackThreshold?: number;
}

export class Backtester {
  private initialBalance: number;
  private riskPercent: number;
  private commission: number;
  private slippage: number;
  private riskManager: RiskManager;

  constructor(
    initialBalance: number = 10000,
    riskPercent: number = 1, // Defaulting to 1% for professional sizing
    commission: number = 0.0004,
    slippage: number = 0.0001,
    riskConfig?: Partial<RiskConfig>
  ) {
    this.initialBalance = initialBalance;
    this.riskPercent = riskPercent;
    this.commission = commission;
    this.slippage = slippage;
    this.riskManager = new RiskManager({
      maxRiskPerTrade: riskPercent,
      ...riskConfig
    });
  }

  // Load 1H candles for multi-TF bias
  private load1HBias(candles1h: Candle[]): Map<number, { ema20: number; ema50: number; bias: 'LONG' | 'SHORT' | 'NEUTRAL' }> {
    const closes = candles1h.map(c => c.close);
    const ema20 = TechnicalIndicators.calculateEMA(closes, 20);
    const ema50 = TechnicalIndicators.calculateEMA(closes, 50);

    const biasMap = new Map<number, { ema20: number; ema50: number; bias: 'LONG' | 'SHORT' | 'NEUTRAL' }>();

    candles1h.forEach((candle, i) => {
      let bias: 'LONG' | 'SHORT' | 'NEUTRAL' = 'NEUTRAL';
      if (ema20[i] > ema50[i]) bias = 'LONG';
      else if (ema20[i] < ema50[i]) bias = 'SHORT';

      biasMap.set(candle.open_time, { ema20: ema20[i], ema50: ema50[i], bias });
    });

    return biasMap;
  }

  // Helper: Find 1H bias for a 15m candle
  private get1HBias(timestamp15m: number, biasMap: Map<number, any>): 'LONG' | 'SHORT' | 'NEUTRAL' {
    // Round down to nearest hour
    const hour = Math.floor(timestamp15m / (60 * 60 * 1000)) * (60 * 60 * 1000);
    const bias = biasMap.get(hour);
    return bias ? bias.bias : 'NEUTRAL';
  }

  // Strategy 1: Volatility Expansion - V3 (ADVANCED)
  private volatilityExpansionV3(
    candles: Candle[],
    regimes: Map<number, MarketRegime>,
    leverage: number = 1,
    candles1h?: Candle[],
    params?: StrategyParams
  ): Trade[] {
    const compressionPercentile = params?.compressionPercentile ?? 15;
    const volumeSpikeMultiple = params?.volumeSpikeMultiple ?? 1.8; // Tighter
    const tpRR = params?.tpRR ?? 2.5;

    const trades: Trade[] = [];
    const closes = candles.map((c) => c.close);
    const volumes = candles.map((c) => c.volume);

    const ema20 = TechnicalIndicators.calculateEMA(closes, 20);
    const ema50 = TechnicalIndicators.calculateEMA(closes, 50);
    const bb = TechnicalIndicators.calculateBollingerBands(closes, 20, 2);
    const atr = TechnicalIndicators.calculateATR(candles, 14);
    const rsi = TechnicalIndicators.calculateRSI(closes, 14);
    const volumeMA = TechnicalIndicators.calculateSMA(volumes, 20);

    let biasMap: Map<number, any> | undefined;
    if (candles1h) biasMap = this.load1HBias(candles1h);

    let position: { side: 'LONG' | 'SHORT'; entry: number; entryTime: number; stopLoss: number; takeProfit: number; regime: MarketRegime; positionSize: number; riskAmount: number } | null = null;
    let lastTradeExitIndex = -999;

    for (let i = 100; i < candles.length; i++) {
      const currentRegime = regimes.get(candles[i].open_time) || 'RANGING';

      // Dynamic ATR Stop Multiplier based on regime
      let atrStopMult = 1.8;
      if (currentRegime === 'BULL_TREND' || currentRegime === 'BEAR_TREND') atrStopMult = 1.5;
      else if (currentRegime === 'COMPRESSED') atrStopMult = 2.2;
      else if (currentRegime === 'HIGH_VOLATILITY') atrStopMult = 3.0;

      // Check exit
      if (position) {
        const currentPrice = candles[i].close;
        let exitSignal = false;
        let exitPrice = currentPrice;

        if (position.side === 'LONG') {
          if (currentPrice <= position.stopLoss || currentPrice >= position.takeProfit) {
            exitSignal = true;
            exitPrice = currentPrice <= position.stopLoss ? position.stopLoss : position.takeProfit;
          }
        } else {
          if (currentPrice >= position.stopLoss || currentPrice <= position.takeProfit) {
            exitSignal = true;
            exitPrice = currentPrice >= position.stopLoss ? position.stopLoss : position.takeProfit;
          }
        }

        if (exitSignal) {
          exitPrice = exitPrice * (1 + (position.side === 'LONG' ? -this.slippage : this.slippage));
          const pnlPercent = position.side === 'LONG'
            ? ((exitPrice - position.entry) / position.entry) * 100 * leverage
            : ((position.entry - exitPrice) / position.entry) * 100 * leverage;

          const commissionCost = (this.commission * 2) * 100 * leverage;
          const netPnLPercent = pnlPercent - commissionCost;

          // PnL based on position size
          const pnl = (position.positionSize * netPnLPercent / 100);

          trades.push({
            entryTime: position.entryTime,
            entryPrice: position.entry,
            exitTime: candles[i].open_time,
            exitPrice,
            side: position.side,
            pnl,
            pnlPercent: netPnLPercent,
            regime: position.regime,
            strategy: 'VolatilityExpansionV3',
            leverage,
            positionSize: position.positionSize,
            riskAmount: position.riskAmount
          });

          lastTradeExitIndex = i;
          position = null;
        }
      }

      // Check entry
      if (!position && (i - lastTradeExitIndex) >= 8) {
        let mtfBias = 'NEUTRAL';
        if (biasMap) mtfBias = this.get1HBias(candles[i].open_time, biasMap);

        let bias15m = 'NEUTRAL';
        if (ema20[i] > ema50[i]) bias15m = 'LONG';
        else if (ema20[i] < ema50[i]) bias15m = 'SHORT';

        if (biasMap && mtfBias !== bias15m) continue;
        if (bias15m === 'NEUTRAL') continue;

        const bbWidthHistory = bb.width.slice(Math.max(0, i - 100), i + 1).filter(v => !isNaN(v));
        const bbWidthPercentile = TechnicalIndicators.percentileRank(bb.width[i], bbWidthHistory);
        if (bbWidthPercentile > compressionPercentile) continue;

        if (volumes[i] < volumeMA[i] * volumeSpikeMultiple) continue;

        const bodyPercent = (Math.abs(candles[i].close - candles[i].open)) / (candles[i].high - candles[i].low);
        if (bodyPercent < 0.7) continue;

        if (bias15m === 'LONG' && candles[i].close > bb.upper[i]) {
          const sl = candles[i].close - atr[i] * atrStopMult;
          const tp = candles[i].close + (candles[i].close - sl) * tpRR;

          // Regime-aware sizing
          const currentBalance = this.initialBalance + trades.reduce((sum, t) => sum + t.pnl, 0);
          const sizing = this.riskManager.calculatePositionSize(currentBalance, candles[i].close, sl);

          position = {
            side: 'LONG',
            entry: candles[i].close * (1 + this.slippage),
            entryTime: candles[i].open_time,
            stopLoss: sl,
            takeProfit: tp,
            regime: currentRegime as MarketRegime,
            positionSize: sizing.positionSize,
            riskAmount: sizing.riskAmount
          };
        } else if (bias15m === 'SHORT' && candles[i].close < bb.lower[i]) {
          const sl = candles[i].close + atr[i] * atrStopMult;
          const tp = candles[i].close - (sl - candles[i].close) * tpRR;

          const currentBalance = this.initialBalance + trades.reduce((sum, t) => sum + t.pnl, 0);
          const sizing = this.riskManager.calculatePositionSize(currentBalance, candles[i].close, sl);

          position = {
            side: 'SHORT',
            entry: candles[i].close * (1 - this.slippage),
            entryTime: candles[i].open_time,
            stopLoss: sl,
            takeProfit: tp,
            regime: currentRegime as MarketRegime,
            positionSize: sizing.positionSize,
            riskAmount: sizing.riskAmount
          };
        }
      }
    }
    return trades;
  }

  // Strategy 2: Mean Reversion - TIGHTENED
  private meanReversionStrategy(
    candles: Candle[],
    regimes: Map<number, MarketRegime>,
    leverage: number = 1,
    params?: StrategyParams
  ): Trade[] {
    const rsiEntry = params?.rsiEntry ?? 30;
    const maxHoldBars = params?.maxHoldBars ?? 24;
    const atrStopMult = params?.atrStopMultMR ?? 2.0;

    const trades: Trade[] = [];
    const closes = candles.map((c) => c.close);
    const volumes = candles.map((c) => c.volume);

    const bb = TechnicalIndicators.calculateBollingerBands(closes, 20, 2);
    const rsi = TechnicalIndicators.calculateRSI(closes, 14);
    const atr = TechnicalIndicators.calculateATR(candles, 14);
    const volumeMA = TechnicalIndicators.calculateSMA(volumes, 20);

    let position: { side: 'LONG' | 'SHORT'; entry: number; entryTime: number; regime: MarketRegime; stopLoss: number; trailStop?: number; entryIndex: number; positionSize: number; riskAmount: number } | null = null;

    for (let i = 100; i < candles.length; i++) {
      const currentRegime = regimes.get(candles[i].open_time);
      if (!currentRegime) continue;

      // Trade primarily in RANGING regime
      if (currentRegime !== 'RANGING') {
        if (position) {
          const exitPrice = candles[i].close * (1 + (position.side === 'LONG' ? -this.slippage : this.slippage));
          const pnlPercent = position.side === 'LONG'
            ? ((exitPrice - position.entry) / position.entry) * 100 * leverage
            : ((position.entry - exitPrice) / position.entry) * 100 * leverage;

          const commissionCost = (this.commission * 2) * 100 * leverage;
          const netPnLPercent = pnlPercent - commissionCost;
          const pnl = (position.positionSize * netPnLPercent / 100);

          trades.push({
            entryTime: position.entryTime,
            entryPrice: position.entry,
            exitTime: candles[i].open_time,
            exitPrice,
            side: position.side,
            pnl,
            pnlPercent: netPnLPercent,
            regime: position.regime,
            strategy: 'MeanReversion',
            leverage,
            positionSize: position.positionSize,
            riskAmount: position.riskAmount
          });

          position = null;
        }
        continue;
      }

      // Exit conditions
      if (position) {
        let exitSignal = false;
        const barsInTrade = i - position.entryIndex;

        // Check if we're at 1R profit to activate trailing stop
        const currentPnL = position.side === 'LONG'
          ? (candles[i].close - position.entry) / position.entry
          : (position.entry - candles[i].close) / position.entry;

        const riskR = position.side === 'LONG'
          ? (position.entry - position.stopLoss) / position.entry
          : (position.stopLoss - position.entry) / position.entry;

        if (currentPnL >= riskR && !position.trailStop) {
          // Activate trailing stop at breakeven
          position.trailStop = position.entry;
        }

        // Exit at BB middle, trailing stop, hard stop, or max hold time
        if (position.side === 'LONG') {
          if (candles[i].close >= bb.middle[i] ||
            candles[i].close <= position.stopLoss ||
            (position.trailStop && candles[i].close <= position.trailStop) ||
            barsInTrade >= maxHoldBars) {
            exitSignal = true;
          }
        } else if (position.side === 'SHORT') {
          if (candles[i].close <= bb.middle[i] ||
            candles[i].close >= position.stopLoss ||
            (position.trailStop && candles[i].close >= position.trailStop) ||
            barsInTrade >= maxHoldBars) {
            exitSignal = true;
          }
        }

        if (exitSignal) {
          const exitPrice = candles[i].close * (1 + (position.side === 'LONG' ? -this.slippage : this.slippage));
          const pnlPercent = position.side === 'LONG'
            ? ((exitPrice - position.entry) / position.entry) * 100 * leverage
            : ((position.entry - exitPrice) / position.entry) * 100 * leverage;

          const commissionCost = (this.commission * 2) * 100 * leverage;
          const netPnLPercent = pnlPercent - commissionCost;
          const pnl = (position.positionSize * netPnLPercent / 100);

          trades.push({
            entryTime: position.entryTime,
            entryPrice: position.entry,
            exitTime: candles[i].open_time,
            exitPrice,
            side: position.side,
            pnl,
            pnlPercent: netPnLPercent,
            regime: position.regime,
            strategy: 'MeanReversion',
            leverage,
            positionSize: position.positionSize,
            riskAmount: position.riskAmount
          });

          position = null;
        }
      }

      // Entry - TIGHTENED
      if (!position) {
        // BB width check (moderate width, not compressed or too wide)
        const bbWidth = (bb.upper[i] - bb.lower[i]) / bb.middle[i];
        if (bbWidth < 0.01 || bbWidth > 0.08) continue; // Skip extreme BB widths

        // Volume confirmation: decreasing volume = exhaustion
        const volumeDecreasing = i > 0 && volumes[i] < volumes[i - 1];

        // Long at lower BB + RSI < 30
        if (candles[i].close <= bb.lower[i] && rsi[i] < rsiEntry && volumeDecreasing && !isNaN(atr[i])) {
          const stopLoss = candles[i].close - atr[i] * atrStopMult;
          const currentBalance = this.initialBalance + trades.reduce((sum, t) => sum + t.pnl, 0);
          const sizing = this.riskManager.calculatePositionSize(currentBalance, candles[i].close, stopLoss);

          position = {
            side: 'LONG',
            entry: candles[i].close * (1 + this.slippage),
            entryTime: candles[i].open_time,
            regime: currentRegime,
            stopLoss,
            entryIndex: i,
            positionSize: sizing.positionSize,
            riskAmount: sizing.riskAmount
          };
        }
        else if (candles[i].close >= bb.upper[i] && rsi[i] > (100 - rsiEntry) && volumeDecreasing && !isNaN(atr[i])) {
          const stopLoss = candles[i].close + atr[i] * atrStopMult;
          const currentBalance = this.initialBalance + trades.reduce((sum, t) => sum + t.pnl, 0);
          const sizing = this.riskManager.calculatePositionSize(currentBalance, candles[i].close, stopLoss);

          position = {
            side: 'SHORT',
            entry: candles[i].close * (1 - this.slippage),
            entryTime: candles[i].open_time,
            regime: currentRegime,
            stopLoss,
            entryIndex: i,
            positionSize: sizing.positionSize,
            riskAmount: sizing.riskAmount
          };
        }
      }
    }

    return trades;
  }

  // Ensemble Strategy: Confirmation from multiple systems
  private ensembleStrategy(
    candles: Candle[],
    regimes: Map<number, MarketRegime>,
    leverage: number = 1,
    candles1h?: Candle[],
    params?: StrategyParams
  ): Trade[] {
    const compressionPercentile = params?.compressionPercentile ?? 20;
    const volumeSpikeMultiple = params?.volumeSpikeMultiple ?? 1.5;
    const tpRR = params?.tpRR ?? 2.5;

    const trades: Trade[] = [];
    const closes = candles.map((c) => c.close);
    const highs = candles.map((c) => c.high);
    const lows = candles.map((c) => c.low);
    const volumes = candles.map((c) => c.volume);

    // Indicators for all strategies
    const ema20 = TechnicalIndicators.calculateEMA(closes, 20);
    const ema50 = TechnicalIndicators.calculateEMA(closes, 50);
    const bb = TechnicalIndicators.calculateBollingerBands(closes, 20, 2);
    const atr = TechnicalIndicators.calculateATR(candles, 14);
    const rsi = TechnicalIndicators.calculateRSI(closes, 14);
    const { adx } = TechnicalIndicators.calculateADX(highs, lows, closes, 14);
    const volumeMA = TechnicalIndicators.calculateSMA(volumes, 20);

    let biasMap: Map<number, any> | undefined;
    if (candles1h) biasMap = this.load1HBias(candles1h);

    let position: { side: 'LONG' | 'SHORT'; entry: number; entryTime: number; stopLoss: number; takeProfit: number; regime: MarketRegime; positionSize: number; riskAmount: number } | null = null;
    let lastTradeExitIndex = -999;

    for (let i = 100; i < candles.length; i++) {
      const currentRegime = regimes.get(candles[i].open_time) || 'RANGING';

      if (position) {
        // Exit logic (Unified ATR Trailing + Hard SL/TP)
        const currentPrice = candles[i].close;
        let exitSignal = false;
        let exitPrice = currentPrice;

        if (position.side === 'LONG') {
          if (currentPrice <= position.stopLoss || currentPrice >= position.takeProfit) {
            exitSignal = true;
            exitPrice = currentPrice <= position.stopLoss ? position.stopLoss : position.takeProfit;
          }
        } else {
          if (currentPrice >= position.stopLoss || currentPrice <= position.takeProfit) {
            exitSignal = true;
            exitPrice = currentPrice >= position.stopLoss ? position.stopLoss : position.takeProfit;
          }
        }

        if (exitSignal) {
          exitPrice = exitPrice * (1 + (position.side === 'LONG' ? -this.slippage : this.slippage));
          const pnlPercent = position.side === 'LONG'
            ? ((exitPrice - position.entry) / position.entry) * 100 * leverage
            : ((position.entry - exitPrice) / position.entry) * 100 * leverage;

          const commissionCost = (this.commission * 2) * 100 * leverage;
          const netPnLPercent = pnlPercent - commissionCost;
          const pnl = (position.positionSize * netPnLPercent / 100);

          trades.push({
            entryTime: position.entryTime,
            entryPrice: position.entry,
            exitTime: candles[i].open_time,
            exitPrice,
            side: position.side,
            pnl,
            pnlPercent: netPnLPercent,
            regime: position.regime,
            strategy: 'Ensemble',
            leverage,
            positionSize: position.positionSize,
            riskAmount: position.riskAmount
          });

          lastTradeExitIndex = i;
          position = null;
        }
      }

      if (!position && (i - lastTradeExitIndex) >= 5) {
        // Check Strategy Votes
        let longVotes = 0;
        let shortVotes = 0;

        // 1. VolatilityExpansionV3 Vote
        const compressionPercentile = params?.compressionPercentile ?? 20;
        const volumeSpikeMultiple = params?.volumeSpikeMultiple ?? 1.5;

        const bbWidthHistory = bb.width.slice(Math.max(0, i - 100), i + 1).filter(v => !isNaN(v));
        const bbWidthPercentile = TechnicalIndicators.percentileRank(bb.width[i], bbWidthHistory);
        const isCompressed = bbWidthPercentile <= compressionPercentile;
        const volumeSpike = volumes[i] > volumeMA[i] * volumeSpikeMultiple;

        if (isCompressed && volumeSpike) {
          if (candles[i].close > bb.upper[i]) longVotes += 2; // Weighting VolExp higher
          if (candles[i].close < bb.lower[i]) shortVotes += 2;
        }

        // 2. MeanReversion Vote
        const rsiEntry = params?.rsiEntry ?? 30;
        if (currentRegime === 'RANGING') {
          if (rsi[i] < rsiEntry && candles[i].close <= bb.lower[i]) longVotes++;
          if (rsi[i] > (100 - rsiEntry) && candles[i].close >= bb.upper[i]) shortVotes++;
        }

        // 3. Momentum Vote
        const adxThreshold = params?.adxThreshold ?? 25;
        if (adx[i] > adxThreshold) {
          if (ema20[i] > ema50[i] && candles[i].close > ema20[i]) longVotes++;
          if (ema20[i] < ema50[i] && candles[i].close < ema20[i]) shortVotes++;
        }

        // Final Decision
        let finalSide: 'LONG' | 'SHORT' | null = null;
        if (longVotes >= 2) finalSide = 'LONG';
        else if (shortVotes >= 2) finalSide = 'SHORT';

        if (finalSide) {
          // Multi-TF Confluence (Required for Ensemble)
          if (biasMap) {
            const mtfBias = this.get1HBias(candles[i].open_time, biasMap);
            if (mtfBias !== finalSide) finalSide = null;
          }
        }

        if (finalSide) {
          const atrStopMult = params?.atrStopMult ?? (currentRegime === 'HIGH_VOLATILITY' ? 2.5 : 1.8);
          const sl = finalSide === 'LONG' ? candles[i].close - atr[i] * atrStopMult : candles[i].close + atr[i] * atrStopMult;
          const risk = Math.abs(candles[i].close - sl);
          const tp = finalSide === 'LONG' ? candles[i].close + risk * tpRR : candles[i].close - risk * tpRR;

          // Adjust risk based on regime and strength of vote
          const baseRisk = this.riskPercent;
          let multiplier = 1.0;
          if (currentRegime === 'BULL_TREND' || currentRegime === 'BEAR_TREND') multiplier = 1.5;
          else if (currentRegime === 'RANGING') multiplier = 0.5;

          const currentBalance = this.initialBalance + trades.reduce((sum, t) => sum + t.pnl, 0);
          const sizing = this.riskManager.calculatePositionSize(
            currentBalance,
            candles[i].close,
            sl,
            undefined, undefined, undefined,
            (atr[i] / candles[i].close) * 100 // Passing volatility relative to price
          );

          position = {
            side: finalSide,
            entry: candles[i].close * (finalSide === 'LONG' ? (1 + this.slippage) : (1 - this.slippage)),
            entryTime: candles[i].open_time,
            stopLoss: sl,
            takeProfit: tp,
            regime: currentRegime as MarketRegime,
            positionSize: sizing.positionSize,
            riskAmount: sizing.riskAmount
          };
        }
      }
    }
    return trades;
  }

  // Strategy 3: Momentum - V2 (Restored & Updated)
  private momentumStrategy(
    candles: Candle[],
    regimes: Map<number, MarketRegime>,
    leverage: number = 1,
    params?: StrategyParams
  ): Trade[] {
    const adxThreshold = params?.adxThreshold ?? 30;
    const atrTrailMult = params?.atrTrailMult ?? 2.0;

    const trades: Trade[] = [];
    const closes = candles.map((c) => c.close);
    const highs = candles.map((c) => c.high);
    const lows = candles.map((c) => c.low);

    const ema20 = TechnicalIndicators.calculateEMA(closes, 20);
    const ema50 = TechnicalIndicators.calculateEMA(closes, 50);
    const { adx } = TechnicalIndicators.calculateADX(highs, lows, closes, 14);
    const atr = TechnicalIndicators.calculateATR(candles, 14);

    let position: {
      side: 'LONG' | 'SHORT';
      entry: number;
      entryTime: number;
      trailStop: number;
      regime: MarketRegime;
      positionSize: number;
      riskAmount: number;
      entryIndex: number
    } | null = null;

    for (let i = 100; i < candles.length; i++) {
      const currentRegime = regimes.get(candles[i].open_time) || 'RANGING';

      if (position) {
        const currentPrice = candles[i].close;
        let exitSignal = false;
        if (adx[i] < 20) exitSignal = true;

        if (position.side === 'LONG') {
          position.trailStop = Math.max(position.trailStop, currentPrice - atr[i] * 1.5);
          if (currentPrice <= position.trailStop) exitSignal = true;
        } else {
          position.trailStop = Math.min(position.trailStop, currentPrice + atr[i] * 1.5);
          if (currentPrice >= position.trailStop) exitSignal = true;
        }

        if (exitSignal) {
          const exitPrice = currentPrice * (1 + (position.side === 'LONG' ? -this.slippage : this.slippage));
          const pnlPercent = position.side === 'LONG'
            ? ((exitPrice - position.entry) / position.entry) * 100 * leverage
            : ((position.entry - exitPrice) / position.entry) * 100 * leverage;

          const commissionCost = (this.commission * 2) * 100 * leverage;
          const netPnLPercent = pnlPercent - commissionCost;
          const pnl = (position.positionSize * netPnLPercent / 100);

          trades.push({
            entryTime: position.entryTime,
            entryPrice: position.entry,
            exitTime: candles[i].open_time,
            exitPrice,
            side: position.side,
            pnl,
            pnlPercent: netPnLPercent,
            regime: position.regime,
            strategy: 'Momentum',
            leverage,
            positionSize: position.positionSize,
            riskAmount: position.riskAmount
          });
          position = null;
        }
      }

      if (!position && adx[i] > adxThreshold) {
        if (ema20[i] > ema50[i] && (currentRegime === 'BULL_TREND' || currentRegime === 'COMPRESSED')) {
          const sl = candles[i].close - atr[i] * 2;
          const currentBalance = this.initialBalance + trades.reduce((sum, t) => sum + t.pnl, 0);
          const sizing = this.riskManager.calculatePositionSize(currentBalance, candles[i].close, sl);

          position = { side: 'LONG', entry: candles[i].close * (1 + this.slippage), entryTime: candles[i].open_time, trailStop: sl, regime: currentRegime as MarketRegime, positionSize: sizing.positionSize, riskAmount: sizing.riskAmount, entryIndex: i };
        } else if (ema20[i] < ema50[i] && (currentRegime === 'BEAR_TREND' || currentRegime === 'COMPRESSED')) {
          const sl = candles[i].close + atr[i] * 2;
          const currentBalance = this.initialBalance + trades.reduce((sum, t) => sum + t.pnl, 0);
          const sizing = this.riskManager.calculatePositionSize(currentBalance, candles[i].close, sl);

          position = { side: 'SHORT', entry: candles[i].close * (1 - this.slippage), entryTime: candles[i].open_time, trailStop: sl, regime: currentRegime as MarketRegime, positionSize: sizing.positionSize, riskAmount: sizing.riskAmount, entryIndex: i };
        }
      }
    }
    return trades;
  }

  private calculateMetrics(trades: Trade[]): Omit<BacktestResults, 'strategy' | 'regime' | 'leverage' | 'trades'> {
    if (trades.length === 0) {
      return {
        totalPnL: 0,
        totalPnLPercent: 0,
        winRate: 0,
        tradeCount: 0,
        winCount: 0,
        lossCount: 0,
        maxDrawdown: 0,
        sharpeRatio: 0,
        profitFactor: 0,
        avgWin: 0,
        avgLoss: 0,
        largestWin: 0,
        largestLoss: 0,
      };
    }

    const totalPnL = trades.reduce((sum, t) => sum + t.pnl, 0);
    const totalPnLPercent = (totalPnL / this.initialBalance) * 100;
    const winCount = trades.filter((t) => t.pnl > 0).length;
    const lossCount = trades.filter((t) => t.pnl <= 0).length;
    const winRate = (winCount / trades.length) * 100;

    const wins = trades.filter((t) => t.pnl > 0);
    const losses = trades.filter((t) => t.pnl <= 0);
    const avgWin = wins.length > 0 ? wins.reduce((sum, t) => sum + t.pnl, 0) / wins.length : 0;
    const avgLoss = losses.length > 0 ? Math.abs(losses.reduce((sum, t) => sum + t.pnl, 0) / losses.length) : 0;

    const totalGain = wins.reduce((sum, t) => sum + t.pnl, 0);
    const totalLoss = Math.abs(losses.reduce((sum, t) => sum + t.pnl, 0));
    const profitFactor = totalLoss > 0 ? totalGain / totalLoss : totalGain > 0 ? 999 : 0;

    // Max drawdown
    let balance = this.initialBalance;
    let peak = balance;
    let maxDrawdown = 0;

    for (const trade of trades) {
      balance += trade.pnl;
      if (balance > peak) peak = balance;
      const drawdown = ((peak - balance) / peak) * 100;
      if (drawdown > maxDrawdown) maxDrawdown = drawdown;
    }

    // Sharpe ratio (simplified)
    const returns = trades.map((t) => t.pnlPercent);
    const avgReturn = returns.reduce((sum, r) => sum + r, 0) / returns.length;
    const stdDev = Math.sqrt(
      returns.reduce((sum, r) => sum + Math.pow(r - avgReturn, 2), 0) / returns.length
    );
    const sharpeRatio = stdDev > 0 ? (avgReturn / stdDev) * Math.sqrt(252) : 0;

    const largestWin = wins.length > 0 ? Math.max(...wins.map((t) => t.pnl)) : 0;
    const largestLoss = losses.length > 0 ? Math.min(...losses.map((t) => t.pnl)) : 0;

    return {
      totalPnL,
      totalPnLPercent,
      winRate,
      tradeCount: trades.length,
      winCount,
      lossCount,
      maxDrawdown,
      sharpeRatio,
      profitFactor,
      avgWin,
      avgLoss,
      largestWin,
      largestLoss,
    };
  }

  runBacktest(
    candles: Candle[],
    strategy: 'VolatilityExpansion' | 'VolatilityExpansionV3' | 'MeanReversion' | 'Momentum' | 'Ensemble',
    leverage: number = 1,
    regimeFilter?: MarketRegime,
    precomputedRegimeMap?: Map<number, MarketRegime>,
    candles1h?: Candle[],
    params?: StrategyParams
  ): BacktestResults {
    // Use precomputed regimes or classify
    let regimeMap: Map<number, MarketRegime>;
    if (precomputedRegimeMap) {
      regimeMap = precomputedRegimeMap;
    } else {
      const regimeData = RegimeClassifier.classifyAllRegimes(candles);
      regimeMap = new Map<number, MarketRegime>();
      regimeData.forEach((r) => regimeMap.set(r.timestamp, r.regime));
    }

    // Run strategy
    let allTrades: Trade[];
    if (strategy === 'VolatilityExpansion') {
      allTrades = this.volatilityExpansionV3(candles, regimeMap, leverage, candles1h, params);
    } else if (strategy === 'VolatilityExpansionV3') {
      allTrades = this.volatilityExpansionV3(candles, regimeMap, leverage, candles1h, params);
    } else if (strategy === 'MeanReversion') {
      allTrades = this.meanReversionStrategy(candles, regimeMap, leverage, params);
    } else if (strategy === 'Ensemble') {
      allTrades = this.ensembleStrategy(candles, regimeMap, leverage, candles1h, params);
    } else {
      allTrades = this.momentumStrategy(candles, regimeMap, leverage, params);
    }

    // Filter trades by regime if specified
    const trades = regimeFilter
      ? allTrades.filter((t) => t.regime === regimeFilter)
      : allTrades;

    const metrics = this.calculateMetrics(trades);

    return {
      strategy,
      regime: regimeFilter || 'ALL',
      leverage,
      trades,
      ...metrics,
    };
  }
}
