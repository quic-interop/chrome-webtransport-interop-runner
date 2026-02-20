function base64ToArrayBuffer(base64) {
    var binaryString = atob(base64);
    var bytes = new Uint8Array(binaryString.length);
    for (var i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes.buffer;
}

async function runHandshake(url, certhash, protocols) {
    const transport = new WebTransport(url, {
        "serverCertificateHashes": [{ "algorithm": "sha-256", "value": base64ToArrayBuffer(certhash) }],
        "protocols": protocols
    });
    await transport.ready;
    const protocol = transport.protocol;
    return { protocol: protocol };
}

async function handleIncomingPushes(transport, expectedCount, results) {
    const reader = transport.incomingUnidirectionalStreams.getReader();
    const processingPromises = [];

    for (let i = 0; i < expectedCount; i++) {
        // We must await the next stream object from the queue...
        let stream, done;
        try {
            const result = await reader.read();
            stream = result.value;
            done = result.done;
        } catch (err) {
            // Server may close the connection after sending all streams; treat as no more streams.
            const msg = (err && (err.message || String(err))) || "";
            if (/connection lost|closed|aborted/i.test(msg)) {
                break;
            }
            throw err;
        }
        if (done) break;

        // ...but we don't await the processing. 
        // We start it immediately and store the promise to track completion.
        const p = (async () => {
            try {
                const { filename, data } = await processIncomingStream(stream);
                results[filename] = Array.from(data);
                console.log(`[Uni] Finished: ${filename} (${data.length} bytes)`);
            } catch (err) {
                console.error("[Uni] Stream processing failed:", err);
            }
        })();
        
        processingPromises.push(p);
    }

    // Now we wait for all background workers to finish
    await Promise.all(processingPromises);
    reader.releaseLock();
}

async function runTransferUnidirectional(url, certhash, protocols, filenames) {
    const transport = new WebTransport(url, {
        "serverCertificateHashes": [{ "algorithm": "sha-256", "value": base64ToArrayBuffer(certhash) }],
        "protocols": protocols
    });
    await transport.ready;

    const results = {};
    
    // launch the listener and handle requests in parallel
    const receivePromise = handleIncomingPushes(transport, filenames.length, results);
    const requestPromises = filenames.map(file => sendGetRequest(transport, file));

    // wait for all GETs to be sent and all PUSHes to be fully read
    await Promise.all([...requestPromises, receivePromise]);
    
    const protocol = transport.protocol;
    return { protocol:protocol, files: results };
}

async function readHeader(reader) {
    let buffer = new Uint8Array(0);
    while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        let newBuffer = new Uint8Array(buffer.length + value.length);
        newBuffer.set(buffer);
        newBuffer.set(value, buffer.length);
        buffer = newBuffer;

        const newlineIndex = buffer.indexOf(10); // 10 is '\n'
        if (newlineIndex !== -1) {
            return {
                header: buffer.slice(0, newlineIndex),
                remainingBuffer: buffer.slice(newlineIndex + 1)
            };
        }
    }
    return { header: buffer, remainingBuffer: new Uint8Array(0) };
}

// reads header and body of a single stream
async function processIncomingStream(stream) {
    const reader = stream.getReader();
    try {
        const { header, remainingBuffer } = await readHeader(reader);
        const filename = new TextDecoder().decode(header).replace("PUSH ", "").trim();

        const chunks = [];
        if (remainingBuffer.length > 0) chunks.push(remainingBuffer);

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            chunks.push(value);
        }

        // merge chunks into one Uint8Array
        const totalLength = chunks.reduce((acc, curr) => acc + curr.length, 0);
        const data = new Uint8Array(totalLength);
        let offset = 0;
        for (const chunk of chunks) {
            data.set(chunk, offset);
            offset += chunk.length;
        }

        return { filename, data };
    } finally {
        reader.releaseLock();
    }
}

// opens a unidirectional stream and sends the "GET <filename>" command
async function sendGetRequest(transport, filename) {
    const stream = await transport.createUnidirectionalStream();
    const writer = stream.getWriter();
    const encoder = new TextEncoder();
    
    await writer.write(encoder.encode(`GET ${filename}`));
    await writer.close();
}

// Transfer test: respond to GET requests on unidirectional or bidirectional streams
// filesByFilename: { filename: array of byte values }
async function runTransfer(url, certhash, protocols, filesByFilename) {
    const transport = new WebTransport(url, {
        "serverCertificateHashes": [{ "algorithm": "sha-256", "value": base64ToArrayBuffer(certhash) }],
        "protocols": protocols
    });
    await transport.ready;

    const decodedFiles = {};
    for (const [name, arr] of Object.entries(filesByFilename)) {
        decodedFiles[name] = new Uint8Array(arr);
    }

    const uniPromise = handleTransferUnidirectionalStreams(transport, decodedFiles);
    const biPromise = handleTransferBidirectionalStreams(transport, decodedFiles);

    await Promise.all([uniPromise, biPromise]);

    const protocol = transport.protocol;
    return { protocol };
}

async function handleTransferUnidirectionalStreams(transport, decodedFiles) {
    const reader = transport.incomingUnidirectionalStreams.getReader();
    const pushPromises = [];

    while (true) {
        let stream, done;
        try {
            const result = await reader.read();
            stream = result.value;
            done = result.done;
        } catch (err) {
            // the server closes the connection after receiving all PUSHes
            const msg = (err && (err.message || String(err))) || "";
            if (/connection lost|closed|aborted/i.test(msg)) {
                break;
            }
            throw err;
        }
        if (done) break;

        const p = (async () => {
            try {
                const filename = await readGetRequest(stream);
                if (!filename || !decodedFiles[filename]) {
                    console.error(`[Transfer Uni] Unknown or missing file: ${filename}`);
                    return;
                }
                const data = decodedFiles[filename];
                const pushStream = await transport.createUnidirectionalStream();
                const writer = pushStream.getWriter();
                const encoder = new TextEncoder();
                await writer.write(encoder.encode(`PUSH ${filename}\n`));
                await writer.write(data);
                await writer.close();
                console.log(`[Transfer Uni] PUSH sent: ${filename} (${data.length} bytes)`);
            } catch (err) {
                console.error("[Transfer Uni] Request handling failed:", err);
            }
        })();
        pushPromises.push(p);
    }

    await Promise.all(pushPromises);
    reader.releaseLock();
}

async function handleTransferBidirectionalStreams(transport, decodedFiles) {
    const reader = transport.incomingBidirectionalStreams.getReader();
    const responsePromises = [];

    while (true) {
        let stream, done;
        try {
            const result = await reader.read();
            stream = result.value;
            done = result.done;
        } catch (err) {
            const msg = (err && (err.message || String(err))) || "";
            if (/connection lost|closed|aborted/i.test(msg)) {
                break;
            }
            throw err;
        }
        if (done) break;

        const p = (async () => {
            const writer = stream.writable.getWriter();
            try {
                const filename = await readGetRequest(stream.readable);
                if (!filename || !decodedFiles[filename]) {
                    console.error(`[Transfer Bi] Unknown or missing file: ${filename}`);
                    return;
                }
                const data = decodedFiles[filename];
                await writer.write(data);
                console.log(`[Transfer Bi] Sent on same stream: ${filename} (${data.length} bytes)`);
            } catch (err) {
                console.error("[Transfer Bi] Request handling failed:", err);
            } finally {
                await writer.close();
            }
        })();
        responsePromises.push(p);
    }

    await Promise.all(responsePromises);
    reader.releaseLock();
}

async function readGetRequest(stream) {
    const reader = stream.getReader();
    const chunks = [];
    try {
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            chunks.push(value);
        }
        const totalLength = chunks.reduce((acc, c) => acc + c.length, 0);
        const buffer = new Uint8Array(totalLength);
        let offset = 0;
        for (const chunk of chunks) {
            buffer.set(chunk, offset);
            offset += chunk.length;
        }
        const request = new TextDecoder().decode(buffer).trim();
        if (request.startsWith("GET ")) {
            return request.slice(4).trim();
        }
        return null;
    } finally {
        reader.releaseLock();
    }
}
