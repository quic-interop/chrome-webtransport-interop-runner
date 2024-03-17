function base64ToArrayBuffer(base64) {
    var binaryString = atob(base64);
    var bytes = new Uint8Array(binaryString.length);
    for (var i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes.buffer;
}

async function establishSession(url) {
    const transport = new WebTransport(url, {
        "serverCertificateHashes": [{
            "algorithm": "sha-256",
            "value": base64ToArrayBuffer("%%CERTHASH%%")
        }]
    });

    transport.closed.then(() => {
        console.log(`The HTTP/3 connection to ${url} closed gracefully.`);
    }).catch((error) => {
        console.error(`The HTTP/3 connection to ${url} closed due to ${error}.`);
    });

    // Once .ready fulfills, the connection can be used.
    await transport.ready;
    return transport;
}

async function readFromStream(reader) {
    let chunks = [];
    let totalLength = 0;

    while (true) {
        const { value, done } = await reader.read();
        if (done) { break; }
        chunks.push(value);
        totalLength += value.length;
    }

    // Combine all chunks into a single Uint8Array
    let data = new Uint8Array(totalLength);
    let position = 0;
    for (let chunk of chunks) {
        data.set(chunk, position);
        position += chunk.length;
    }
    return data
}

async function request(path) {
    const transport = await establishSession('https://%%SERVER%%/webtransport');
    const data = new TextEncoder().encode("GET " + path + "\r\n");

    const { writable, readable } = await transport.createBidirectionalStream();
    console.log("Opened stream.");

    const writer = writable.getWriter();
    await writer.write(data);
    try {
        await writer.close();
        console.log("All data has been sent on stream.");
    } catch(error) {
        console.error(`An error occurred: ${error}`);
    }

    const rsp = await readFromStream(readable.getReader());
    transport.close();
    return rsp;
}

