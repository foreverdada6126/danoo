export interface Candle {
  open_time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  close_time: number;
}

export class TechnicalIndicators {
  static calculateEMA(data: number[], period: number): number[] {
    const ema: number[] = [];
    const multiplier = 2 / (period + 1);
    ema[0] = data[0];

    for (let i = 1; i < data.length; i++) {
      ema[i] = (data[i] - ema[i - 1]) * multiplier + ema[i - 1];
    }

    return ema;
  }

  static calculateSMA(data: number[], period: number): number[] {
    const sma: number[] = new Array(data.length).fill(NaN);
    if (data.length < period) return sma;

    let sum = 0;
    for (let i = 0; i < period; i++) {
      sum += data[i];
    }
    sma[period - 1] = sum / period;

    for (let i = period; i < data.length; i++) {
      sum = sum - data[i - period] + data[i];
      sma[i] = sum / period;
    }

    return sma;
  }

  static calculateBollingerBands(
    closes: number[],
    period: number,
    stdDev: number
  ): { upper: number[]; middle: number[]; lower: number[]; width: number[] } {
    const middle = this.calculateSMA(closes, period);
    const upper: number[] = new Array(closes.length).fill(NaN);
    const lower: number[] = new Array(closes.length).fill(NaN);
    const width: number[] = new Array(closes.length).fill(NaN);

    if (closes.length < period) return { upper, middle, lower, width };

    for (let i = period - 1; i < closes.length; i++) {
      const slice = closes.slice(i - period + 1, i + 1);
      const mean = middle[i];

      let squareDiffSum = 0;
      for (let j = 0; j < slice.length; j++) {
        squareDiffSum += Math.pow(slice[j] - mean, 2);
      }
      const variance = squareDiffSum / period;
      const std = Math.sqrt(variance);

      upper[i] = mean + stdDev * std;
      lower[i] = mean - stdDev * std;
      width[i] = upper[i] - lower[i];
    }

    return { upper, middle, lower, width };
  }

  static calculateATR(candles: Candle[], period: number): number[] {
    const atr: number[] = [];
    const trueRanges: number[] = [];

    for (let i = 0; i < candles.length; i++) {
      if (i === 0) {
        trueRanges[i] = candles[i].high - candles[i].low;
      } else {
        const highLow = candles[i].high - candles[i].low;
        const highClose = Math.abs(candles[i].high - candles[i - 1].close);
        const lowClose = Math.abs(candles[i].low - candles[i - 1].close);
        trueRanges[i] = Math.max(highLow, highClose, lowClose);
      }
    }

    for (let i = 0; i < trueRanges.length; i++) {
      if (i < period - 1) {
        atr[i] = NaN;
      } else if (i === period - 1) {
        atr[i] = trueRanges.slice(0, period).reduce((a, b) => a + b, 0) / period;
      } else {
        atr[i] = (atr[i - 1] * (period - 1) + trueRanges[i]) / period;
      }
    }

    return atr;
  }

  static calculateRSI(closes: number[], period: number = 14): number[] {
    const rsi: number[] = [];
    const gains: number[] = [];
    const losses: number[] = [];

    for (let i = 1; i < closes.length; i++) {
      const change = closes[i] - closes[i - 1];
      gains.push(change > 0 ? change : 0);
      losses.push(change < 0 ? Math.abs(change) : 0);
    }

    let avgGain = 0;
    let avgLoss = 0;

    for (let i = 0; i < gains.length; i++) {
      if (i < period - 1) {
        rsi.push(NaN);
      } else if (i === period - 1) {
        avgGain = gains.slice(0, period).reduce((a, b) => a + b, 0) / period;
        avgLoss = losses.slice(0, period).reduce((a, b) => a + b, 0) / period;
        const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
        rsi.push(100 - 100 / (1 + rs));
      } else {
        avgGain = (avgGain * (period - 1) + gains[i]) / period;
        avgLoss = (avgLoss * (period - 1) + losses[i]) / period;
        const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
        rsi.push(100 - 100 / (1 + rs));
      }
    }

    return [NaN, ...rsi];
  }

  static calculateADX(
    highs: number[],
    lows: number[],
    closes: number[],
    period: number = 14
  ): { adx: number[]; plusDi: number[]; minusDi: number[] } {
    const adx: number[] = [];
    const plusDi: number[] = [];
    const minusDi: number[] = [];
    const plusDM: number[] = [];
    const minusDM: number[] = [];
    const trueRanges: number[] = [];

    for (let i = 1; i < highs.length; i++) {
      const highDiff = highs[i] - highs[i - 1];
      const lowDiff = lows[i - 1] - lows[i];

      plusDM.push(highDiff > lowDiff && highDiff > 0 ? highDiff : 0);
      minusDM.push(lowDiff > highDiff && lowDiff > 0 ? lowDiff : 0);

      const tr = Math.max(
        highs[i] - lows[i],
        Math.abs(highs[i] - closes[i - 1]),
        Math.abs(lows[i] - closes[i - 1])
      );
      trueRanges.push(tr);
    }

    let smoothedTR = 0;
    let smoothedPlusDM = 0;
    let smoothedMinusDM = 0;

    for (let i = 0; i < closes.length; i++) {
      if (i < period) {
        adx.push(NaN);
        plusDi.push(NaN);
        minusDi.push(NaN);
      } else if (i === period) {
        smoothedTR = trueRanges.slice(0, period).reduce((a, b) => a + b, 0);
        smoothedPlusDM = plusDM.slice(0, period).reduce((a, b) => a + b, 0);
        smoothedMinusDM = minusDM.slice(0, period).reduce((a, b) => a + b, 0);

        const plusDI = smoothedTR > 0 ? (smoothedPlusDM / smoothedTR) * 100 : 0;
        const minusDI = smoothedTR > 0 ? (smoothedMinusDM / smoothedTR) * 100 : 0;

        plusDi.push(plusDI);
        minusDi.push(minusDI);

        const diSum = plusDI + minusDI;
        const dx = diSum > 0 ? (Math.abs(plusDI - minusDI) / diSum) * 100 : 0;
        adx.push(dx);
      } else {
        smoothedTR = smoothedTR - smoothedTR / period + trueRanges[i - 1];
        smoothedPlusDM = smoothedPlusDM - smoothedPlusDM / period + plusDM[i - 1];
        smoothedMinusDM = smoothedMinusDM - smoothedMinusDM / period + minusDM[i - 1];

        const plusDI = smoothedTR > 0 ? (smoothedPlusDM / smoothedTR) * 100 : 0;
        const minusDI = smoothedTR > 0 ? (smoothedMinusDM / smoothedTR) * 100 : 0;

        plusDi.push(plusDI);
        minusDi.push(minusDI);

        const diSum = plusDI + minusDI;
        const dx = diSum > 0 ? (Math.abs(plusDI - minusDI) / diSum) * 100 : 0;

        const prevAdx = adx[i - 1];
        adx.push((prevAdx * (period - 1) + dx) / period);
      }
    }

    return { adx, plusDi, minusDi };
  }

  static percentileRank(value: number, array: number[]): number {
    let count = 0;
    for (const v of array) {
      if (!isNaN(v) && v < value) count++;
    }
    return (count / array.filter(v => !isNaN(v)).length) * 100;
  }
}
