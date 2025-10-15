// epfl-hierarchical-scraper.js
const puppeteer = require('puppeteer');
const fs = require('fs-extra');
const path = require('path');
const dotenv = require('dotenv');
const { setTimeout } = require('timers/promises');
const crypto = require('crypto');
const { URL } = require('url');
const https = require('https');
const http = require('http');

// Load environment variables
const envPath = path.resolve(__dirname, '../.env');
dotenv.config({ path: envPath });

// Check credentials
if (!process.env.EPFL_USERNAME_TEQUILA || !process.env.EPFL_USERNAME_MICROSOFT || !process.env.EPFL_PASSWORD) {
  console.error('Error: EPFL_USERNAME_TEQUILA, EPFL_USERNAME_MICROSOFT, and EPFL_PASSWORD must be defined in .env file');
  process.exit(1);
}

// Parse command line arguments for root URLs
const getCommandLineUrls = () => {
  const args = process.argv.slice(2); // Remove 'node' and script name
  if (args.length > 0) {
    console.log('Using URLs from command line arguments');
    return args.filter(arg => arg.startsWith('http'));
  }
  return null;
};

const commandLineUrls = getCommandLineUrls();

// Configuration
const config = {
  // Root URLs to scrape - only pages under these paths will be scraped
  // Can be overridden by command line arguments
  rootUrls: commandLineUrls || [
    'https://www.epfl.ch/campus/services/',
    'https://www.epfl.ch/about/'
  ],

  outputDir: path.join(__dirname, 'epfl_hierarchical_data'),

  credentials: {
    usernameTequila: process.env.EPFL_USERNAME_TEQUILA,
    usernameMicrosoft: process.env.EPFL_USERNAME_MICROSOFT,
    password: process.env.EPFL_PASSWORD
  },

  crawling: {
    maxDepth: 15,
    maxPages: 100000,
    concurrentPages: 3,
    relaunchBrowserAfterPages: 100,
    relaunchBrowserAfterHours: 2,

    // File types to download
    downloadableFileTypes: [
      '.pdf', '.doc', '.docx', '.ppt', '.pptx',
      '.xls', '.xlsx', '.zip', '.rar', '.csv'
    ],

    excludePatterns: [
      /\.(jpg|jpeg|png|gif|svg|ico|webp|bmp)$/i,
      /\.(mp4|avi|mov|wmv|flv|webm)$/i,
      /\.(mp3|wav|ogg|flac)$/i,
      /\/logout/i,
      /\/signout/i,
      /\/deconnexion/i,
      /mailto:/i,
      /tel:/i,
    ]
  },

  delays: {
    navigation: 3000,
    typing: 100,
    download: 5000,
    randomMin: 500,
    randomMax: 2000,
  },

  userAgents: [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0'
  ]
};

// Global variables
let lastBrowserLaunchTime = Date.now();
let pagesSinceLastBrowserLaunch = 0;

// Utilities
function getRandomDelay() {
  return Math.floor(Math.random() * (config.delays.randomMax - config.delays.randomMin + 1)) + config.delays.randomMin;
}

function getRandomUserAgent() {
  return config.userAgents[Math.floor(Math.random() * config.userAgents.length)];
}

async function waitRandomTime(baseTime = 0) {
  const randomTime = getRandomDelay();
  await setTimeout(baseTime + randomTime);
}

function normalizeUrl(urlStr) {
  try {
    const urlObj = new URL(urlStr);
    urlObj.hash = '';
    urlObj.searchParams.sort();
    return urlObj.toString();
  } catch (e) {
    return urlStr;
  }
}

function isUnderRootUrl(url) {
  try {
    const normalizedUrl = normalizeUrl(url);
    return config.rootUrls.some(rootUrl => normalizedUrl.startsWith(rootUrl));
  } catch (e) {
    return false;
  }
}

function isAllowedUrl(url, currentUrl = null) {
  try {
    const absoluteUrlStr = currentUrl ? new URL(url, currentUrl).toString() : new URL(url).toString();
    const urlObj = new URL(absoluteUrlStr);

    // Must be under one of the root URLs
    if (!isUnderRootUrl(absoluteUrlStr)) {
      return false;
    }

    // Check exclude patterns
    const isExcludedByPattern = config.crawling.excludePatterns.some(pattern =>
      pattern.test(absoluteUrlStr)
    );
    if (isExcludedByPattern) {
      return false;
    }

    return true;
  } catch (e) {
    return false;
  }
}

function isDownloadableFile(url) {
  const urlPath = new URL(url).pathname.toLowerCase();
  return config.crawling.downloadableFileTypes.some(ext => urlPath.endsWith(ext));
}

// Convert URL to folder path that mirrors site structure
function urlToFolderPath(url, baseOutputDir) {
  const urlObj = new URL(url);
  let pathParts = urlObj.pathname.split('/').filter(Boolean);

  // Remove trailing index.html or similar
  if (pathParts.length > 0 && pathParts[pathParts.length - 1].match(/\.(html?|php|asp)$/i)) {
    pathParts.pop();
  }

  // Create safe folder names
  pathParts = pathParts.map(part =>
    part.replace(/[^a-z0-9_-]/gi, '_').substring(0, 100)
  );

  // Add a hash to ensure uniqueness if needed
  const hash = crypto.createHash('md5').update(url).digest('hex').substring(0, 8);

  return path.join(baseOutputDir, ...pathParts, hash);
}

// Get safe filename for a document
function getSafeFileName(url) {
  const urlObj = new URL(url);
  const fileName = path.basename(urlObj.pathname);
  return fileName.replace(/[^a-z0-9_.-]/gi, '_');
}

// Crawler State Management
class CrawlerState {
  constructor(stateFile) {
    this.stateFile = stateFile;
    this.visited = new Set();
    this.toVisit = new Map();
    this.failed = new Map();
    this.load();
  }

  load() {
    if (fs.existsSync(this.stateFile)) {
      try {
        const state = fs.readJSONSync(this.stateFile);
        this.visited = new Set(state.visited || []);
        this.toVisit = new Map(state.toVisit || []);
        this.failed = new Map(state.failed || []);
        console.log(`Loaded state: ${this.visited.size} visited, ${this.toVisit.size} to visit`);
      } catch (error) {
        console.error('Error loading state:', error);
      }
    }
  }

  save() {
    const state = {
      visited: Array.from(this.visited),
      toVisit: Array.from(this.toVisit),
      failed: Array.from(this.failed),
      lastUpdated: new Date().toISOString()
    };
    try {
      fs.writeJSONSync(this.stateFile, state, { spaces: 2 });
    } catch (error) {
      console.error('Error saving state:', error);
    }
  }

  addUrl(url, referrer = null, currentDepth = 0) {
    const normalized = normalizeUrl(url);
    if (!normalized) return;

    if (this.visited.has(normalized) || this.toVisit.has(normalized)) {
      return;
    }
    this.toVisit.set(normalized, { referrer, addedAt: new Date().toISOString(), depth: currentDepth });
  }

  getNextUrl() {
    if (this.toVisit.size === 0) return null;
    const [url, metadata] = this.toVisit.entries().next().value;
    this.toVisit.delete(url);
    return { url, metadata };
  }

  markVisited(url) {
    this.visited.add(normalizeUrl(url));
  }

  markFailed(url, error, referrer = null) {
    const normalized = normalizeUrl(url);
    this.failed.set(normalized, {
      error: error.message,
      timestamp: new Date().toISOString(),
      referrer: referrer
    });
  }
}

// Authentication handler (same as your original)
async function authenticateEPFL(page, currentAttemptUrl) {
  console.log('Starting EPFL authentication process...');

  try {
    if (!page.url().includes('login') && !page.url().includes('tequila') && !page.url().includes('microsoftonline')) {
      console.log(`Not on a login page. Navigating to inside.epfl.ch to trigger login...`);
      await page.goto('https://inside.epfl.ch', { waitUntil: 'networkidle2', timeout: 45000 });
      await waitRandomTime(config.delays.navigation);
    }

    const isAlreadyLoggedIn = await page.evaluate(() =>
      document.body.innerText.toLowerCase().includes('logout') ||
      document.body.innerText.toLowerCase().includes('déconnexion') ||
      document.querySelector('.user-logged-in, [class*="logged-in"], [data-test-id="logout-button"]')
    );

    if (isAlreadyLoggedIn) {
      console.log('Already authenticated.');
      if (normalizeUrl(page.url()) !== normalizeUrl(currentAttemptUrl)) {
        await page.goto(currentAttemptUrl, { waitUntil: 'networkidle2', timeout: 60000 });
      }
      return;
    }

    // TEQUILA LOGIN
    if (page.url().includes('tequila.epfl.ch')) {
      console.log('Detected Tequila login form.');
      await page.waitForSelector('#username', { timeout: 15000, visible: true });
      await page.type('#username', config.credentials.usernameTequila, { delay: config.delays.typing });
      await page.type('#password', config.credentials.password, { delay: config.delays.typing });
      await waitRandomTime(500);

      const tequilaLoginSelectors = ['#loginbutton', 'input[type="image"][name="login"]', 'button[type="submit"]'];
      let tequilaLoginClicked = false;

      for (const selector of tequilaLoginSelectors) {
        try {
          await page.waitForSelector(selector, { timeout: 3000, visible: true });
          await Promise.all([
            page.waitForNavigation({ waitUntil: 'load', timeout: 60000 }),
            page.click(selector)
          ]);
          tequilaLoginClicked = true;
          await setTimeout(1500);
          break;
        } catch (e) {
          continue;
        }
      }

      if (!tequilaLoginClicked) {
        throw new Error('Could not click Tequila login button');
      }
    }

    // MICROSOFT LOGIN
    if (page.url().includes('login.microsoftonline.com')) {
      console.log('Detected Microsoft login form.');

      if (await page.$('#i0116')) {
        try {
          await page.waitForSelector('#i0116', { timeout: 20000, visible: true });
          await page.type('#i0116', config.credentials.usernameMicrosoft + "@epfl.ch", { delay: config.delays.typing });
          await waitRandomTime(500);
          await Promise.all([
            page.waitForNavigation({ waitUntil: 'networkidle0', timeout: 60000 }),
            page.click('#idSIButton9')
          ]);
        } catch (e) {
          console.log('Microsoft email field interaction issue:', e.message);
        }
      }

      if (await page.$('#i0118')) {
        try {
          await page.waitForSelector('#i0118', { timeout: 20000, visible: true });
          await page.type('#i0118', config.credentials.password, { delay: config.delays.typing });
          await waitRandomTime(500);
          await Promise.all([
            page.waitForNavigation({ waitUntil: 'networkidle0', timeout: 60000 }),
            page.click('#idSIButton9')
          ]);
        } catch (e) {
          console.log('Microsoft password field interaction issue:', e.message);
        }
      }

      try {
        console.log('Checking for MFA...');
        await page.waitForFunction(() => {
          const textIndicators = ['verify your identity', 'approve', 'authenticator'];
          const pageText = document.body.innerText.toLowerCase();
          return textIndicators.some(text => pageText.includes(text));
        }, { timeout: 20000 });

        console.log('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!');
        console.log('!! MFA REQUIRED: Check your Microsoft Authenticator app');
        console.log('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!');

        await page.waitForNavigation({ waitUntil: 'networkidle0', timeout: 120000 });
      } catch (e) {
        console.log('No MFA or already completed');
      }

      if (page.url().includes('login.microsoftonline.com') || page.url().includes('kmsi')) {
        try {
          const staySignedInButton = await page.waitForSelector('#idSIButton9', { timeout: 15000, visible: true });
          if (staySignedInButton) {
            await Promise.all([
              page.waitForNavigation({ waitUntil: 'networkidle0', timeout: 60000 }),
              staySignedInButton.click()
            ]);
          }
        } catch (e) {
          console.log('Stay signed in prompt not found');
        }
      }
    }

    await page.waitForFunction(
      () => {
        const currentHref = window.location.href;
        const onEpflDomain = currentHref.includes('.epfl.ch');
        const notOnLoginPages = !currentHref.includes('login.') &&
                                !currentHref.includes('tequila.epfl.ch') &&
                                !currentHref.includes('microsoftonline.com');
        return (onEpflDomain && notOnLoginPages);
      },
      { timeout: 60000 }
    );

    if (normalizeUrl(page.url()) !== normalizeUrl(currentAttemptUrl)) {
      await page.goto(currentAttemptUrl, { waitUntil: 'networkidle2', timeout: 60000 });
    }

  } catch (error) {
    console.error(`Authentication failed: ${error.message}`);
    const screenshotPath = path.join(config.outputDir, `auth_error_${Date.now()}.png`);
    try {
      if (!page.isClosed()) {
        await page.screenshot({ path: screenshotPath, fullPage: true });
      }
    } catch (ssError) {
      console.error('Failed to take screenshot');
    }
    throw error;
  }
}

async function downloadFile(page, url, targetDir) {
  const fileName = getSafeFileName(url);
  const filePath = path.join(targetDir, fileName);

  console.log(`  Downloading: ${fileName}`);

  try {
    const cookiesArray = await page.cookies(url);
    const cookieHeader = cookiesArray.map(cookie => `${cookie.name}=${cookie.value}`).join('; ');
    const urlObj = new URL(url);

    const options = {
      hostname: urlObj.hostname,
      path: urlObj.pathname + urlObj.search,
      method: 'GET',
      headers: {
        'User-Agent': getRandomUserAgent(),
        'Cookie': cookieHeader,
      },
      rejectUnauthorized: true,
    };

    const requester = urlObj.protocol === 'https:' ? https : http;

    await new Promise((resolve, reject) => {
      const request = requester.get(options, (response) => {
        if (response.statusCode !== 200) {
          reject(new Error(`Failed to download. Status: ${response.statusCode}`));
          response.resume();
          return;
        }

        const fileStream = fs.createWriteStream(filePath);
        response.pipe(fileStream);

        fileStream.on('finish', () => {
          fileStream.close(() => {
            resolve();
          });
        });

        fileStream.on('error', (err) => {
          fs.unlink(filePath, () => {});
          reject(err);
        });
      });

      request.on('error', (err) => {
        reject(err);
      });

      request.setTimeout(config.delays.download * 2, () => {
        request.destroy();
        reject(new Error('Request timeout'));
      });

      request.end();
    });

    if (fs.existsSync(filePath)) {
      const stats = fs.statSync(filePath);
      console.log(`    ✓ Downloaded: ${fileName} (${(stats.size / 1024).toFixed(2)} KB)`);
      return fileName;
    }

  } catch (error) {
    console.error(`    ✗ Failed to download ${fileName}: ${error.message}`);
    return null;
  }
}

async function extractLinksFromPage(page) {
  return await page.evaluate(() => {
    const links = [];
    document.querySelectorAll('a[href]').forEach(a => {
      try {
        const href = new URL(a.getAttribute('href'), document.baseURI).toString();
        if (!href.startsWith('javascript:') && !href.startsWith('mailto:') && !href.startsWith('tel:')) {
          links.push({
            href: href,
            text: a.innerText.trim()
          });
        }
      } catch (e) {}
    });
    return links;
  });
}

async function crawlPage(browser, state, urlInfo, currentDepth = 0) {
  const { url, metadata } = urlInfo;
  const referrer = metadata ? metadata.referrer : null;

  if (currentDepth > config.crawling.maxDepth) {
    console.log(`Skipping ${url} - max depth exceeded.`);
    return;
  }

  if (state.visited.size >= config.crawling.maxPages) {
    console.log('Max pages reached.');
    return;
  }

  const page = await browser.newPage();
  await page.setUserAgent(getRandomUserAgent());
  await page.setDefaultNavigationTimeout(60000);
  await page.setDefaultTimeout(45000);

  try {
    console.log(`\n[${state.visited.size + 1}] Crawling: ${url}`);
    console.log(`  Depth: ${currentDepth}, From: ${referrer || 'root'}`);

    const response = await page.goto(url, { waitUntil: 'networkidle2' });

    if (!response) {
      throw new Error('Navigation returned no response.');
    }

    const status = response.status();
    if (status === 404) {
      console.log(`  ✗ 404 Not Found`);
      state.markFailed(url, new Error('404 Not Found'), referrer);
      return;
    } else if (status >= 400) {
      console.log(`  ✗ HTTP Error ${status}`);
      state.markFailed(url, new Error(`HTTP ${status}`), referrer);
      return;
    }

    // Check authentication
    const needsAuth = page.url().includes('login.') || page.url().includes('tequila') || page.url().includes('microsoftonline');
    if (needsAuth) {
      await authenticateEPFL(page, url);
    }

    await waitRandomTime(config.delays.navigation / 2);

    // Create folder for this page
    const pageFolder = urlToFolderPath(url, config.outputDir);
    fs.ensureDirSync(pageFolder);

    // Save HTML
    const htmlContent = await page.content();
    const htmlPath = path.join(pageFolder, 'page.html');
    fs.writeFileSync(htmlPath, htmlContent);
    console.log(`  ✓ Saved HTML`);

    // Extract all links
    const allLinks = await extractLinksFromPage(page);
    console.log(`  Found ${allLinks.length} links`);

    // Separate HTML pages from downloadable documents
    const htmlLinks = [];
    const documentLinks = [];

    for (const link of allLinks) {
      if (isDownloadableFile(link.href)) {
        documentLinks.push(link);
      } else if (isAllowedUrl(link.href, url)) {
        htmlLinks.push(link);
      }
    }

    // Download all documents linked from this page
    const downloadedFiles = [];
    if (documentLinks.length > 0) {
      console.log(`  Downloading ${documentLinks.length} documents...`);
      for (const docLink of documentLinks) {
        const fileName = await downloadFile(page, docLink.href, pageFolder);
        if (fileName) {
          downloadedFiles.push({
            fileName: fileName,
            originalUrl: docLink.href,
            linkText: docLink.text
          });
        }
      }
    }

    // Create metadata file
    const metadata = {
      url: url,
      crawledAt: new Date().toISOString(),
      title: await page.title(),
      depth: currentDepth,
      referrer: referrer,
      htmlFile: 'page.html',
      downloadedDocuments: downloadedFiles,
      htmlLinks: htmlLinks.map(l => ({ url: l.href, text: l.text })),
      status: status
    };

    const metadataPath = path.join(pageFolder, 'metadata.json');
    fs.writeJSONSync(metadataPath, metadata, { spaces: 2 });
    console.log(`  ✓ Saved metadata (${downloadedFiles.length} documents downloaded)`);

    state.markVisited(url);
    pagesSinceLastBrowserLaunch++;

    // Add new HTML links to queue
    if (currentDepth < config.crawling.maxDepth) {
      let addedLinks = 0;
      for (const link of htmlLinks) {
        const absoluteLink = normalizeUrl(link.href);
        if (absoluteLink && !state.visited.has(absoluteLink) && !state.toVisit.has(absoluteLink)) {
          state.addUrl(absoluteLink, url, currentDepth + 1);
          addedLinks++;
        }
      }
      console.log(`  ✓ Added ${addedLinks} new pages to queue`);
    }

    state.save();

  } catch (error) {
    console.error(`  ✗ Error: ${error.message}`);
    state.markFailed(url, error, referrer);
    state.save();
  } finally {
    try {
      await page.goto('about:blank');
      await page.close();
    } catch (closeError) {
      console.error('Error closing page:', closeError.message);
    }
  }
}

class CrawlerPool {
  constructor(state, concurrency) {
    this.state = state;
    this.concurrency = concurrency;
    this.activeCrawlers = 0;
    this.browser = null;
    this.shouldStop = false;
  }

  async launchBrowser() {
    console.log("\n=== Launching browser ===");
    if (this.browser) {
      try { await this.browser.close(); } catch (e) {}
    }
    this.browser = await puppeteer.launch({
      headless: true,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-accelerated-2d-canvas',
        '--disable-gpu',
        '--window-size=1920x1080',
      ],
      defaultViewport: { width: 1920, height: 1080 },
      protocolTimeout: 60000
    });

    this.browser.on('disconnected', () => {
      console.warn('Browser disconnected');
      this.browser = null;
    });

    lastBrowserLaunchTime = Date.now();
    pagesSinceLastBrowserLaunch = 0;
    return this.browser;
  }

  async needsBrowserRestart() {
    if (!this.browser || !this.browser.isConnected()) return true;
    if (pagesSinceLastBrowserLaunch >= config.crawling.relaunchBrowserAfterPages) return true;
    const hoursSinceLastLaunch = (Date.now() - lastBrowserLaunchTime) / (1000 * 60 * 60);
    if (hoursSinceLastLaunch >= config.crawling.relaunchBrowserAfterHours) return true;
    return false;
  }

  async run() {
    this.shouldStop = false;
    if (!this.browser || !(await this.browser.isConnected()) || await this.needsBrowserRestart()) {
      await this.launchBrowser();
    }

    const processNext = async () => {
      if (this.shouldStop) {
        this.activeCrawlers--;
        if (this.activeCrawlers === 0) this.finalizeRun();
        return;
      }

      if (await this.needsBrowserRestart() && this.activeCrawlers === 0) {
        await this.launchBrowser();
      }

      if (!this.browser || !this.browser.isConnected()) {
        if (this.activeCrawlers === 0) await this.launchBrowser();
        else {
          await setTimeout(5000);
          this.activeCrawlers--;
          if (this.activeCrawlers < this.concurrency) processQueue();
          return;
        }
      }

      if (this.state.visited.size >= config.crawling.maxPages) {
        this.shouldStop = true;
        this.activeCrawlers--;
        if (this.activeCrawlers === 0) this.finalizeRun();
        return;
      }

      const urlInfo = this.state.getNextUrl();
      if (urlInfo) {
        await crawlPage(this.browser, this.state, urlInfo, urlInfo.metadata.depth)
          .catch(e => console.error(`Error in crawlPage: ${e.message}`))
          .finally(() => {
            this.activeCrawlers--;
            if (!this.shouldStop && this.activeCrawlers < this.concurrency) {
              processQueue();
            } else if (this.activeCrawlers === 0 && (this.shouldStop || this.state.toVisit.size === 0)) {
              this.finalizeRun();
            }
          });
      } else {
        this.activeCrawlers--;
        if (this.activeCrawlers === 0) this.finalizeRun();
      }
    };

    const processQueue = () => {
      while (this.activeCrawlers < this.concurrency && this.state.toVisit.size > 0 && !this.shouldStop) {
        if (this.state.visited.size >= config.crawling.maxPages) {
          this.shouldStop = true;
          break;
        }
        this.activeCrawlers++;
        processNext();
      }
      if (this.activeCrawlers === 0 && (this.shouldStop || this.state.toVisit.size === 0)) {
        this.finalizeRun();
      }
    };

    this.finalizeRun = () => {
      if (!this.finalizing) {
        this.finalizing = true;
        console.log("\n=== Crawl completed ===");
        if (this.onFinishedCallback) this.onFinishedCallback();
      }
    };

    processQueue();

    return new Promise(resolve => {
      this.onFinishedCallback = resolve;
      if (this.activeCrawlers === 0 && (this.shouldStop || this.state.toVisit.size === 0)) {
        this.finalizeRun();
      }
    });
  }

  async stop() {
    console.log("Stopping crawler...");
    this.shouldStop = true;
  }
}

async function main() {
  console.log('=================================================');
  console.log('EPFL Hierarchical Site Scraper');
  console.log('=================================================');
  console.log(`Output directory: ${config.outputDir}`);
  console.log(`Root URLs:`);
  config.rootUrls.forEach(url => console.log(`  - ${url}`));
  console.log('=================================================\n');

  fs.ensureDirSync(config.outputDir);

  const stateFile = path.join(config.outputDir, 'crawler_state.json');
  const state = new CrawlerState(stateFile);

  if (state.toVisit.size === 0 && state.visited.size === 0) {
    config.rootUrls.forEach(url => state.addUrl(url, null, 0));
    state.save();
  }

  const logFile = path.join(config.outputDir, 'crawler.log');
  const originalConsoleLog = console.log;
  const originalConsoleError = console.error;

  const logToFile = (level, ...args) => {
    const message = args.map(arg => typeof arg === 'string' ? arg : JSON.stringify(arg)).join(' ');
    const logMessage = `[${new Date().toISOString()}] [${level}] ${message}\n`;
    fs.appendFileSync(logFile, logMessage);
    if (level === 'ERROR') originalConsoleError.apply(console, args);
    else originalConsoleLog.apply(console, args);
  };

  console.log = (...args) => logToFile('INFO', ...args);
  console.error = (...args) => logToFile('ERROR', ...args);

  const pool = new CrawlerPool(state, config.crawling.concurrentPages);

  process.on('SIGINT', async () => {
    console.log("\nSIGINT received. Shutting down...");
    await pool.stop();
    setTimeout(async () => {
      if (pool.browser && pool.browser.isConnected()) {
        await pool.browser.close();
      }
      process.exit(0);
    }, 30000);
  });

  await pool.run();

  if (pool.browser && pool.browser.isConnected()) {
    await pool.browser.close();
  }

  state.save();

  console.log('\n=================================================');
  console.log('CRAWL SUMMARY');
  console.log('=================================================');
  console.log(`Total pages visited: ${state.visited.size}`);
  console.log(`Failed pages: ${state.failed.size}`);
  console.log(`Pages in queue: ${state.toVisit.size}`);
  console.log('=================================================');

  const report = {
    totalPagesVisited: state.visited.size,
    failedPages: state.failed.size,
    remainingQueue: state.toVisit.size,
    crawlEndTime: new Date().toISOString(),
    rootUrls: config.rootUrls
  };

  fs.writeJSONSync(path.join(config.outputDir, 'summary.json'), report, { spaces: 2 });
}

main().catch(error => {
  console.error('Fatal error:', error);
  process.exit(1);
});