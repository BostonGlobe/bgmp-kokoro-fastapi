const fs = require("node:fs");
const path = require("node:path");
const ENV_PATH = path.join(__dirname, ".env.qa");

function loadDotEnv(filePath) {
    if (!fs.existsSync(filePath)) {
        return;
    }

    const contents = fs.readFileSync(filePath, "utf8");
    for (const line of contents.split(/\r?\n/)) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith("#")) {
            continue;
        }

        const equalsIndex = trimmed.indexOf("=");
        if (equalsIndex === -1) {
            continue;
        }

        const key = trimmed.slice(0, equalsIndex).trim();
        const value = trimmed.slice(equalsIndex + 1).trim();

        if (key && process.env[key] === undefined) {
            process.env[key] = value;
        }
    }
}

loadDotEnv(ENV_PATH);

const ARTICLE_ID = "IGAZUGISZZHLVD22LRIRKLZKO4";
const PRODUCT = "globe";
const API_BASE_URL = process.env.KOKORO_API_BASE_URL;
const SPEECH_ENDPOINT_URL = `${API_BASE_URL}/v1/audio/speech`;
const DOWNLOAD_ENDPOINT_URL = `${API_BASE_URL}/v1/download/${ARTICLE_ID}.mp3?product=${PRODUCT}`;
const ARTICLE_PATH = path.join(__dirname, "articles", `${ARTICLE_ID}.txt`);
const DOWNLOAD_OUTPUT_PATH = path.join(__dirname, `audio/${ARTICLE_ID}.mp3`);

async function readArticleText() {
    return fs.promises.readFile(ARTICLE_PATH, "utf8");
}

function buildRequestBody(input) {
    return {
        product: PRODUCT,
        article_id: ARTICLE_ID,
        model: "kokoro",
        input,
        voice: "af_alloy",
        response_format: "mp3",
        download_format: "mp3",
        speed: 1,
        stream: true,
        return_download_link: true,
        lang_code: "a",
        volume_multiplier: 1,
        normalization_options: {
            normalize: true,
            unit_normalization: false,
            url_normalization: true,
            email_normalization: true,
            optional_pluralization_normalization: true,
            phone_normalization: true,
            replace_remaining_symbols: true,
            html_normalization: true,
            punctuation_pacing_normalization: true,
            month_abbreviation_normalization: true,
            pronunciation_normalization: true,
            score_normalization: true,
            number_abbreviation_normalization: true,
        },
    };
}

async function consumeStreamingResponse(response) {
    if (!response.body) {
        throw new Error("Response body is empty");
    }

    const reader = response.body.getReader();
    let chunkCount = 0;
    let totalBytes = 0;

    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) {
                break;
            }

            chunkCount += 1;
            totalBytes += value.byteLength;
        }
    } finally {
        reader.releaseLock();
    }

    return { chunkCount, totalBytes };
}

async function saveResponseToFile(response, outputPath) {
    if (!response.body) {
        throw new Error("Response body is empty");
    }

    const reader = response.body.getReader();
    const output = fs.createWriteStream(outputPath);
    let chunkCount = 0;
    let totalBytes = 0;

    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) {
                break;
            }

            chunkCount += 1;
            totalBytes += value.byteLength;

            if (!output.write(Buffer.from(value))) {
                await new Promise((resolve, reject) => {
                    output.once("drain", resolve);
                    output.once("error", reject);
                });
            }
        }

        await new Promise((resolve, reject) => {
            output.end((error) => {
                if (error) {
                    reject(error);
                    return;
                }
                resolve();
            });
            output.once("error", reject);
        });
    } catch (error) {
        output.destroy(error);
        throw error;
    } finally {
        reader.releaseLock();
    }

    return { chunkCount, totalBytes };
}

async function fetchDownloadPath() {
    console.log(`Fetching download endpoint ${DOWNLOAD_ENDPOINT_URL}`);

    const response = await fetch(DOWNLOAD_ENDPOINT_URL);
    console.log(`Download status: ${response.status} ${response.statusText}`);
    console.log(
        `Download Content-Type: ${response.headers.get("content-type") || "n/a"}`,
    );
    console.log(
        `Download Content-Disposition: ${response.headers.get("content-disposition") || "n/a"}`,
    );

    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Download request failed: ${errorText}`);
    }

    const { chunkCount, totalBytes } = await saveResponseToFile(
        response,
        DOWNLOAD_OUTPUT_PATH,
    );
    console.log(
        `Download stream completed after ${chunkCount} chunks and ${totalBytes} bytes`,
    );
    console.log(`Saved download response to ${DOWNLOAD_OUTPUT_PATH}`);
}

async function main() {
    const input = await readArticleText();
    const requestBody = buildRequestBody(input);

    console.log(`Posting ${ARTICLE_ID} to ${SPEECH_ENDPOINT_URL}`);

    const response = await fetch(SPEECH_ENDPOINT_URL, {
        method: "POST",
        headers: {
            "content-type": "application/json",
        },
        body: JSON.stringify(requestBody),
    });

    console.log(`Status: ${response.status} ${response.statusText}`);
    console.log(`Content-Type: ${response.headers.get("content-type") || "n/a"}`);
    console.log(`Transfer-Encoding: ${response.headers.get("transfer-encoding") || "n/a"}`);
    console.log(`X-Download-Path: ${response.headers.get("x-download-path") || "n/a"}`);
    console.log(`X-Download-Status: ${response.headers.get("x-download-status") || "n/a"}`);

    if (!response.ok) {
        const errorText = await response.text();
        if (errorText.includes("punctuation_pacing_normalization")) {
            console.error(
                "The API schema may expect normalization_options.punctuation_pacing_normalization instead of comma_pacing_normalization.",
            );
        }
        throw new Error(`Request failed: ${errorText}`);
    }

    const { chunkCount, totalBytes } = await consumeStreamingResponse(response);
    console.log(`Stream completed after ${chunkCount} chunks and ${totalBytes} bytes`);
    await fetchDownloadPath();
}

main().catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
});
