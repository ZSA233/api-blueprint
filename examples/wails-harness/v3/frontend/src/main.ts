import { ensureWailsRuntime } from "../../../../typescript/api/(shared)/(wailsv3)/transport";
import { createClients as createApiClients } from "../../../../typescript/api/(wailsv3)";
import { createClients as createStaticClients } from "../../../../typescript/static/(wailsv3)";

async function main(): Promise<void> {
  await ensureWailsRuntime();

  const { helloClient } = createApiClients();
  const { staticClient } = createStaticClients();

  const app = document.querySelector<HTMLDivElement>("#app");

  if (!app) {
    throw new Error("missing #app mount point");
  }

  app.innerHTML = `
  <main style="font-family: ui-sans-serif, system-ui, sans-serif; max-width: 960px; margin: 0 auto; padding: 32px;">
    <h1 style="margin: 0 0 12px;">api-blueprint Wails v3 Harness</h1>
    <p style="margin: 0 0 24px; color: #4b5563;">
      This frontend keeps using the generated Wails overlay clients directly, while the Wails app shell
      stays hand-written and repo-owned.
    </p>
    <div style="display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 24px;">
      <button id="hello-map-enum" type="button">Call hello.mapEnum()</button>
      <button id="static-dochaha" type="button">Call static.dochaha()</button>
    </div>
    <pre id="output" style="background: #111827; color: #f9fafb; padding: 16px; border-radius: 12px; min-height: 240px; overflow: auto;"></pre>
  </main>
`;

  const output = document.querySelector<HTMLPreElement>("#output");

  if (!output) {
    throw new Error("missing #output");
  }

  async function run(label: string, action: () => Promise<unknown>): Promise<void> {
    output.textContent = `${label}\n\nRunning...`;
    try {
      const result = await action();
      output.textContent = `${label}\n\n${JSON.stringify(result, null, 2)}`;
    } catch (error) {
      output.textContent = `${label}\n\n${error instanceof Error ? error.stack ?? error.message : String(error)}`;
    }
  }

  document.querySelector<HTMLButtonElement>("#hello-map-enum")?.addEventListener("click", () => {
    void run("hello.mapEnum()", () => helloClient.mapEnum());
  });

  document.querySelector<HTMLButtonElement>("#static-dochaha")?.addEventListener("click", () => {
    void run("static.dochaha()", () => staticClient.dochaha());
  });
}

void main();
