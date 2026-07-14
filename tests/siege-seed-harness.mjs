#!/usr/bin/env node

import { mkdir, readdir, readFile, writeFile } from 'node:fs/promises';
import { resolve, join, basename, dirname } from 'node:path';
import { Readable } from 'node:stream';

function usage() {
  return `Usage:
  node siege-seed-harness.mjs --base-url https://qa.example.com [options]
  node siege-seed-harness.mjs --articles-dir ./articles [options]

Options:
  --articles-dir <path> Directory of .txt articles to turn into post-urls.txt
  --post-urls-path <p>  Output path for generated post-urls.txt. Default: ./urls/post-urls.txt
  --get-urls-path <p>   Output path for generated get-urls.txt. Default: ./urls/get-urls.txt
  --count <n>          Number of POST seeds to create. Default: 25
  --concurrency <n>    Concurrent POSTs during seeding. Default: 2
  --out-dir <path>     Output directory for generated files. Default: ./urls
  --seed <n>           RNG seed for reproducible article generation. Default: 1337
  --text-field <name>  JSON/form field name for the article text. Default: text
  --payload-mode <m>   json | form | raw. Default: json
  --post-path <path>   POST endpoint path. Default: /v1/audio/speech
  --get-path <path>    GET endpoint path. Default: /v1/download
  --help               Show this message
`;
}

function parseArgs(argv) {
  const args = {
    articlesDir: '',
    postUrlsPath: './urls/post-urls.txt',
    getUrlsPath: './urls/get-urls.txt',
    count: 25,
    concurrency: 2,
    outDir: './urls',
    seed: 1337,
    textField: 'text',
    payloadMode: 'json',
    postPath: '/v1/audio/speech',
    getPath: '/v1/download',
    baseUrl: '',
  };

  for (let i = 2; i < argv.length; i += 1) {
    const token = argv[i];
    if (token === '--help' || token === '-h') {
      args.help = true;
      continue;
    }
    const next = argv[i + 1];
    switch (token) {
      case '--base-url':
        args.baseUrl = next;
        i += 1;
        break;
      case '--articles-dir':
        args.articlesDir = next;
        i += 1;
        break;
      case '--post-urls-path':
        args.postUrlsPath = next;
        i += 1;
        break;
      case '--count':
        args.count = Number(next);
        i += 1;
        break;
      case '--concurrency':
        args.concurrency = Number(next);
        i += 1;
        break;
      case '--out-dir':
        args.outDir = next;
        i += 1;
        break;
      case '--seed':
        args.seed = Number(next);
        i += 1;
        break;
      case '--text-field':
        args.textField = next;
        i += 1;
        break;
      case '--payload-mode':
        args.payloadMode = next;
        i += 1;
        break;
      case '--post-path':
        args.postPath = next;
        i += 1;
        break;
      case '--get-path':
        args.getPath = next;
        i += 1;
        break;
      default:
        throw new Error(`Unknown argument: ${token}`);
    }
  }

  if (args.help) {
    return args;
  }

  if (!args.baseUrl && !args.articlesDir) {
    throw new Error('Either --base-url or --articles-dir is required');
  }

  if (args.baseUrl) {
    try {
      new URL(args.baseUrl);
    } catch {
      throw new Error('--base-url must be a valid URL');
    }
  }

  if (args.articlesDir) {
    args.articlesDir = resolve(args.articlesDir);
  }

  args.postUrlsPath = resolve(args.postUrlsPath);
  args.outDir = resolve(args.outDir);

  if (!Number.isInteger(args.count) || args.count <= 0) {
    throw new Error('--count must be a positive integer');
  }
  if (!Number.isInteger(args.concurrency) || args.concurrency <= 0) {
    throw new Error('--concurrency must be a positive integer');
  }
  if (!Number.isInteger(args.seed)) {
    throw new Error('--seed must be an integer');
  }
  if (!['json', 'form', 'raw'].includes(args.payloadMode)) {
    throw new Error('--payload-mode must be json, form, or raw');
  }

  return args;
}

async function loadArticleFiles(articlesDir) {
  const entries = await readdir(articlesDir, { withFileTypes: true });
  const files = entries
    .filter((entry) => entry.isFile() && entry.name.toLowerCase().endsWith('.txt'))
    .map((entry) => resolve(articlesDir, entry.name))
    .sort((left, right) => left.localeCompare(right));

  const articles = [];
  for (const filePath of files) {
    const content = await readFile(filePath, 'utf8');
    articles.push({
      articleId: basename(filePath, ".txt"),
      content,
      filePath,
    });
  }

  return articles;
}

async function buildPostUrlsFromArticles(articlesDir, postUrlsPath, host) {
  const articles = await loadArticleFiles(articlesDir);
  if (articles.length === 0) {
    throw new Error(`No .txt files found in ${articlesDir}`);
  }

  const payloadsDir = join(dirname(postUrlsPath), 'post-payloads');
  await mkdir(payloadsDir, { recursive: true });

  const lines = articles.map(async (article) => {
    const payload = {
      article_id: article.articleId,
      product: 'test',
      input: article.content,
      voice: 'af_alloy',
      speed: 1,
      return_download_link: true,
      lang_code: 'a',
      normalization_options: {
        normalize: true,
      },
    };

    const payloadPath = join(payloadsDir, `${article.articleId}.json`);
    await writeFile(payloadPath, `${JSON.stringify(payload, null, 2)}\n`);
    return `${host}/v1/audio/speech POST <${payloadPath}>`;
  });

  const resolvedLines = await Promise.all(lines);

  await mkdir(dirname(postUrlsPath), { recursive: true });
  await writeFile(postUrlsPath, `${resolvedLines.join('\n')}\n`);

  return { articleCount: articles.length, postUrlsPath };
}

async function buildGetUrlsFromArticles(articlesDir, getUrlsPath, host) {
  const articles = await loadArticleFiles(articlesDir);
  if (articles.length === 0) {
    throw new Error(`No .txt files found in ${articlesDir}`);
  }

  const lines = articles.map((article) => {

    return `${host}/v1/download/${encodeURIComponent(article.articleId)}.mp3?product=test`;
  });

  await mkdir(dirname(getUrlsPath), { recursive: true });
  await writeFile(getUrlsPath, `${lines.join('\n')}\n`);

  return { articleCount: articles.length, getUrlsPath };
}

function makeRng(seed) {
  let state = seed >>> 0;
  return () => {
    state ^= state << 13;
    state ^= state >>> 17;
    state ^= state << 5;
    return (state >>> 0) / 0x100000000;
  };
}

function pickWeightedBand(rng) {
  const roll = rng();
  if (roll < 0.65) return 'small';
  if (roll < 0.85) return 'medium';
  if (roll < 0.95) return 'large';
  return 'extreme';
}

function wordCountForBand(band, rng) {
  const ranges = {
    small: [300, 900],
    medium: [901, 5000],
    large: [5001, 15000],
    extreme: [15001, 51000],
  };
  const [min, max] = ranges[band];
  return Math.floor(min + rng() * (max - min + 1));
}

function generateArticleText(wordCount, rng) {
  const leadIns = [
    'The article examines the latest developments and their practical impact.',
    'This report summarizes the core ideas, evidence, and implications.',
    'The discussion below presents the topic in a clear and structured way.',
    'The following narrative expands on the main themes and supporting details.',
  ];
  const sentences = [
    'It starts by establishing the background and the most relevant context.',
    'It then moves through the main argument in a steady and readable sequence.',
    'Each section adds detail while keeping the larger story easy to follow.',
    'The conclusion ties the individual points back to the central theme.',
    'Readers should come away with a practical understanding of the subject.',
    'The phrasing remains simple enough to resemble a real article draft.',
    'The content is intentionally varied so the generated text does not feel repetitive.',
    'A few short transitions help the flow remain natural across longer passages.',
  ];

  const words = [];
  const lead = leadIns[Math.floor(rng() * leadIns.length)];
  words.push(...lead.replace(/[^\w\s]/g, '').split(/\s+/));

  while (words.length < wordCount) {
    const sentence = sentences[Math.floor(rng() * sentences.length)];
    words.push(...sentence.replace(/[^\w\s]/g, '').split(/\s+/));
  }

  return words.slice(0, wordCount).join(' ');
}

function normalizeBaseUrl(input) {
  const url = new URL(input);
  return url.origin;
}

function buildUrl(baseUrl, path) {
  const cleanBase = baseUrl.replace(/\/$/, '');
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${cleanBase}${cleanPath}`;
}

function parseFilenameFromHeaders(headers) {
  const candidates = [
    'content-disposition',
    'x-filename',
    'x-file-name',
    'x-download-filename',
    'location',
  ];

  for (const key of candidates) {
    const value = headers.get(key);
    if (!value) continue;

    const dispositionMatch = /filename\*?=(?:UTF-8''|")?([^";\n]+)"?/i.exec(value);
    if (dispositionMatch) {
      return decodeURIComponent(dispositionMatch[1].trim());
    }

    const trimmed = value.trim();
    if (trimmed) {
      try {
        const parsed = new URL(trimmed);
        const parts = parsed.pathname.split('/').filter(Boolean);
        if (parts.length > 0) {
          return decodeURIComponent(parts[parts.length - 1]);
        }
      } catch {
        return trimmed;
      }
    }
  }

  return null;
}

async function parseFilenameFromBody(response) {
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    return null;
  }

  try {
    const payload = await response.clone().json();
    const keys = ['filename', 'file_name', 'download_filename', 'downloadUrl', 'download_url', 'url', 'path'];
    for (const key of keys) {
      const value = payload?.[key];
      if (typeof value === 'string' && value.trim()) {
        if (key === 'url' || key === 'downloadUrl' || key === 'download_url' || key === 'path') {
          try {
            const parsed = new URL(value, 'http://placeholder.local');
            const parts = parsed.pathname.split('/').filter(Boolean);
            if (parts.length > 0) {
              return decodeURIComponent(parts[parts.length - 1]);
            }
          } catch {
            return value.trim();
          }
        }
        return value.trim();
      }
    }
  } catch {
    return null;
  }

  return null;
}

async function drainResponseBody(response) {
  if (!response.body) {
    return 0;
  }

  const stream = Readable.fromWeb(response.body);
  let bytes = 0;
  for await (const chunk of stream) {
    bytes += chunk.length;
  }
  return bytes;
}

function encodeFilenameForPath(filename) {
  return filename.split('/').map((part) => encodeURIComponent(part)).join('/');
}

async function ensureDir(path) {
  await mkdir(path, { recursive: true });
}

async function main() {
    const args = parseArgs(process.argv);
    if (args.help) {
        process.stdout.write(usage());
        process.exit(0);
    }

    await ensureDir(args.outDir);

    const post = await buildPostUrlsFromArticles(args.articlesDir, args.postUrlsPath, args.baseUrl);
    process.stdout.write([
        `Generated post URLs from ${post.articleCount} article files.`,
        `post-urls.txt: ${post.postUrlsPath}`,
    ].join('\n') + '\n');

    const get = await buildGetUrlsFromArticles(args.articlesDir, args.getUrlsPath, args.baseUrl);
    process.stdout.write([
        `Generated get URLs from ${get.articleCount} article files.`,
        `get-urls.txt: ${get.getUrlsPath}`,
    ].join('\n') + '\n');

//   if (!args.baseUrl) {
//     return;
//   }

//   const baseUrl = normalizeBaseUrl(args.baseUrl);
//   const postUrl = buildUrl(baseUrl, args.postPath);
//   const getBasePath = args.getPath.replace(/\/$/, '');
//   const outDir = args.outDir;

//   const rng = makeRng(args.seed);
//   const results = new Array(args.count);

//   let nextIndex = 0;
//   async function worker() {
//     while (true) {
//       const index = nextIndex;
//       nextIndex += 1;
//       if (index >= args.count) {
//         return;
//       }

//       const band = pickWeightedBand(rng);
//       const wordCount = wordCountForBand(band, rng);
//       const articleText = generateArticleText(wordCount, rng);
//       const startedAt = Date.now();

//       const headers = { accept: '*/*' };
//       let body;
//       if (args.payloadMode === 'json') {
//         headers['content-type'] = 'application/json';
//         body = JSON.stringify({ [args.textField]: articleText });
//       } else if (args.payloadMode === 'form') {
//         headers['content-type'] = 'application/x-www-form-urlencoded';
//         body = new URLSearchParams({ [args.textField]: articleText }).toString();
//       } else {
//         headers['content-type'] = 'text/plain; charset=utf-8';
//         body = articleText;
//       }

//       const response = await fetch(postUrl, {
//         method: 'POST',
//         headers,
//         body,
//       });

//       const filenameFromHeaders = parseFilenameFromHeaders(response.headers);
//       const filenameFromBody = filenameFromHeaders || await parseFilenameFromBody(response);
//       const responseBytes = await drainResponseBody(response);
//       const elapsedMs = Date.now() - startedAt;
//       const filename = filenameFromBody || `seed-${String(index + 1).padStart(4, '0')}.mp3`;

//       results[index] = {
//         index: index + 1,
//         band,
//         wordCount,
//         status: response.status,
//         ok: response.ok,
//         filename,
//         responseBytes,
//         elapsedMs,
//         fallbackFilename: !filenameFromHeaders && !filenameFromBody,
//       };
//     }
//   }

//   const workers = Array.from({ length: Math.min(args.concurrency, args.count) }, () => worker());
//   await Promise.all(workers);

//   const filenames = results.map((row) => row.filename);
//   const getUrls = filenames.map((filename) => buildUrl(baseUrl, `${getBasePath}/${encodeFilenameForPath(filename)}`));

//   const reportPath = join(outDir, 'seeding-report.json');
//   const filenamesPath = join(outDir, 'generated-filenames.txt');
//   const getUrlsPath = join(outDir, 'get-urls.txt');

//   await writeFile(reportPath, `${JSON.stringify({ baseUrl, postUrl, getBasePath, ...args, results }, null, 2)}\n`);
//   await writeFile(filenamesPath, `${filenames.join('\n')}\n`);
//   await writeFile(getUrlsPath, `${getUrls.join('\n')}\n`);

//   const fallbackCount = results.filter((row) => row.fallbackFilename).length;
//   const okCount = results.filter((row) => row.ok).length;

//   process.stdout.write([
//     `Seeded ${results.length} POST requests against ${postUrl}.`,
//     `Successful responses: ${okCount}/${results.length}.`,
//     `Generated filenames: ${filenamesPath}`,
//     `Generated GET URLs: ${getUrlsPath}`,
//     `Detailed report: ${reportPath}`,
//     fallbackCount > 0
//       ? `Warning: ${fallbackCount} responses did not expose a filename, so fallback names were used for those rows.`
//       : 'All responses exposed a filename via headers or JSON.',
//   ].join('\n') + '\n');
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exit(1);
});
