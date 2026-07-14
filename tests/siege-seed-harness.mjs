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
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exit(1);
});
