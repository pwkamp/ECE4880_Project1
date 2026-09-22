const host = '127.0.0.1';
const port = Number(process.env.PORT ?? 8787);
const deadline = Date.now() + 30_000;
const url = `http://${host}:${port}/api/health`;

while (Date.now() < deadline) {
  try {
    const response = await fetch(url);
    if (response.ok) process.exit(0);
  } catch {
    // The API process is still loading its MySQL connection.
  }
  await new Promise((resolve) => setTimeout(resolve, 100));
}

console.error(`[frontend] sample API did not become ready at ${url}`);
process.exit(1);
