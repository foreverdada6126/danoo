import fs from 'fs';
import path from 'path';

interface BinanceKline {
  symbol: string;
  timeframe: string;
  open_time: number;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: string;
}

interface Period {
  name: string;
  label: string;
  start: string;
  end: string;
  condition: string;
}

const periods: Period[] = [
  { name: "flash_crash", label: "Extreme Bear (Flash Crash)", start: "2020-02-01", end: "2020-03-31", condition: "bear" },
  { name: "bull_2020", label: "Bullish Uptrend 2020", start: "2020-07-01", end: "2020-09-30", condition: "bull" },
  { name: "capitulation_2022", label: "Capitulation 2022", start: "2022-06-01", end: "2022-07-31", condition: "bear" },
  { name: "institutional_2023", label: "Institutional Accumulation", start: "2023-10-01", end: "2023-12-31", condition: "bull" },
  { name: "correction_2024", label: "Post-ATH Correction", start: "2024-04-01", end: "2024-08-31", condition: "sideways" }
];

const timeframes = ['1m', '3m', '5m', '15m', '1h', '4h'];
const symbol = 'BTCUSDT';
const dataDir = path.join(__dirname, 'data');

async function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function fetchKlines(
  symbol: string,
  interval: string,
  startTime: number,
  endTime: number,
  useFutures: boolean = true
): Promise<any[]> {
  const baseUrl = useFutures
    ? 'https://fapi.binance.com/fapi/v1/klines'
    : 'https://api.binance.com/api/v3/klines';

  const url = `${baseUrl}?symbol=${symbol}&interval=${interval}&startTime=${startTime}&endTime=${endTime}&limit=1500`;

  try {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return await response.json() as any[];
  } catch (error) {
    console.error(`Error fetching from ${useFutures ? 'futures' : 'spot'}:`, error);
    throw error;
  }
}

async function fetchPeriodData(
  symbol: string,
  interval: string,
  startDate: string,
  endDate: string,
  useFutures: boolean = true
): Promise<BinanceKline[]> {
  const startTime = new Date(startDate).getTime();
  const endTime = new Date(endDate).getTime();
  const allData: BinanceKline[] = [];

  let currentStart = startTime;
  let attempts = 0;
  const maxAttempts = 50; // Safety limit

  console.log(`  Fetching ${interval} from ${startDate} to ${endDate}...`);

  while (currentStart < endTime && attempts < maxAttempts) {
    attempts++;

    try {
      const rawKlines = await fetchKlines(symbol, interval, currentStart, endTime, useFutures);

      if (!rawKlines || rawKlines.length === 0) {
        console.log(`  No more data available`);
        break;
      }

      // Transform Binance format to our format
      const klines: BinanceKline[] = rawKlines.map((k: any) => ({
        symbol,
        timeframe: interval,
        open_time: k[0],
        open: k[1],
        high: k[2],
        low: k[3],
        close: k[4],
        volume: k[5]
      }));

      allData.push(...klines);

      // Update start time for next batch
      const lastTime = rawKlines[rawKlines.length - 1][0];
      currentStart = lastTime + 1;

      console.log(`  Fetched ${rawKlines.length} candles (total: ${allData.length})`);

      // Rate limit: wait 200ms between requests
      await sleep(200);

      // If we got less than 1500, we've reached the end
      if (rawKlines.length < 1500) {
        break;
      }
    } catch (error) {
      console.error(`  Error on attempt ${attempts}:`, error);

      // If futures fails on early data, try spot
      if (useFutures && attempts === 1) {
        console.log(`  Retrying with spot API...`);
        return fetchPeriodData(symbol, interval, startDate, endDate, false);
      }

      throw error;
    }
  }

  console.log(`  ✓ Completed: ${allData.length} total candles`);
  return allData;
}

async function main() {
  console.log('🦀 Claw is fetching historical data from Binance...\n');

  // Ensure data directory exists
  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
  }

  // Save periods metadata
  const periodsPath = path.join(dataDir, 'periods.json');
  fs.writeFileSync(periodsPath, JSON.stringify(periods, null, 2));
  console.log(`✓ Saved periods metadata to ${periodsPath}\n`);

  // Fetch data for each period and timeframe
  for (const period of periods) {
    console.log(`\n📊 Period: ${period.label} (${period.name})`);
    console.log(`   Dates: ${period.start} to ${period.end}`);
    console.log(`   Condition: ${period.condition}\n`);

    for (const timeframe of timeframes) {
      try {
        const data = await fetchPeriodData(
          symbol,
          timeframe,
          period.start,
          period.end
        );

        const filename = `${symbol}_${timeframe}_${period.name}.json`;
        const filepath = path.join(dataDir, filename);

        fs.writeFileSync(filepath, JSON.stringify(data, null, 2));
        console.log(`  ✓ Saved ${filename} (${data.length} candles)\n`);
      } catch (error) {
        console.error(`  ✗ Failed to fetch ${timeframe} for ${period.name}:`, error);
      }
    }
  }

  console.log('\n🎉 Data fetching complete!\n');

  // Print summary
  console.log('Summary:');
  const files = fs.readdirSync(dataDir).filter(f => f.endsWith('.json') && f.startsWith('BTCUSDT'));
  files.forEach(file => {
    const filepath = path.join(dataDir, file);
    const data = JSON.parse(fs.readFileSync(filepath, 'utf-8'));
    console.log(`  ${file}: ${data.length} candles`);
  });
}

main().catch(console.error);
