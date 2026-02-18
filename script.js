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
        const { value: stream, done } = await reader.read();
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

function flattenChunks(chunks) {
    const totalLength = chunks.reduce((acc, c) => acc + c.length, 0);
    const data = new Uint8Array(totalLength);
    let offset = 0;
    for (const chunk of chunks) {
        data.set(chunk, offset);
        offset += chunk.length;
    }
    return Array.from(data);
}
