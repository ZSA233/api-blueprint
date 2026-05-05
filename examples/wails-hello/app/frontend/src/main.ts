import { ensureWailsRuntime, WailsV3Transport } from "../../../typescript/api/transports/wailsv3/transport";
import { createClients } from "../../../typescript/api/transports/wailsv3/api";

function extractMessage(response: unknown): string {
  if (response !== null && typeof response === "object") {
    const direct = response as { message?: unknown; data?: unknown };
    if (typeof direct.message === "string") {
      return direct.message;
    }
    if (direct.data !== null && typeof direct.data === "object") {
      const wrapped = direct.data as { message?: unknown };
      if (typeof wrapped.message === "string") {
        return wrapped.message;
      }
    }
  }
  return JSON.stringify(response);
}

async function main(): Promise<void> {
  await ensureWailsRuntime();

  const { helloClient } = createClients({
    transport: new WailsV3Transport(),
  });

  const app = document.querySelector<HTMLDivElement>("#app");
  if (app == null) {
    throw new Error("missing #app mount point");
  }

  app.innerHTML = `
    <main class="shell">
      <section class="hero">
        <p class="eyebrow">Wails-only api-blueprint example</p>
        <h1>Hello from Go, rendered by TypeScript</h1>
        <p class="lede">
          This app does not start an HTTP server. The button calls the generated Wails v3 client,
          which reaches the generated Go binding and the user-owned Go handler.
        </p>
      </section>
      <form id="hello-form" class="card">
        <label for="name">Name</label>
        <div class="row">
          <input id="name" name="name" autocomplete="name" value="Wails" />
          <button type="submit">Say hello</button>
        </div>
      </form>
      <dialog id="hello-dialog">
        <p id="hello-message"></p>
        <form method="dialog">
          <button>Close</button>
        </form>
      </dialog>
    </main>
  `;

  const form = document.querySelector<HTMLFormElement>("#hello-form");
  const input = document.querySelector<HTMLInputElement>("#name");
  const dialog = document.querySelector<HTMLDialogElement>("#hello-dialog");
  const message = document.querySelector<HTMLParagraphElement>("#hello-message");
  if (form == null || input == null || dialog == null || message == null) {
    throw new Error("missing hello form elements");
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    void (async () => {
      const result = await helloClient.greet({
        query: {
          name: input.value,
        },
      });
      const text = extractMessage(result as unknown);
      message.textContent = text;
      if (typeof dialog.showModal === "function") {
        dialog.showModal();
      } else {
        window.alert(text);
      }
    })();
  });
}

const style = document.createElement("style");
style.textContent = `
  :root {
    color: #17130d;
    background: #efe7d2;
    font-family: Avenir Next, Optima, Candara, sans-serif;
  }

  body {
    min-height: 100vh;
    margin: 0;
    background:
      radial-gradient(circle at 20% 15%, rgba(255, 188, 87, 0.45), transparent 28rem),
      linear-gradient(135deg, #f6efd9 0%, #decdb1 100%);
  }

  .shell {
    display: grid;
    gap: 28px;
    max-width: 760px;
    margin: 0 auto;
    padding: 72px 24px;
  }

  .hero h1 {
    max-width: 680px;
    margin: 0;
    font-family: Georgia, Charter, serif;
    font-size: clamp(42px, 8vw, 82px);
    line-height: 0.9;
    letter-spacing: -0.06em;
  }

  .eyebrow {
    margin: 0 0 16px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
  }

  .lede {
    max-width: 620px;
    color: #5f533f;
    font-size: 18px;
    line-height: 1.6;
  }

  .card {
    display: grid;
    gap: 12px;
    padding: 22px;
    border: 1px solid rgba(42, 34, 20, 0.18);
    border-radius: 24px;
    background: rgba(255, 252, 241, 0.7);
    box-shadow: 0 24px 70px rgba(45, 36, 19, 0.18);
    backdrop-filter: blur(16px);
  }

  label {
    font-weight: 700;
  }

  .row {
    display: flex;
    gap: 12px;
  }

  input, button {
    border: 0;
    border-radius: 999px;
    font: inherit;
  }

  input {
    min-width: 0;
    flex: 1;
    padding: 14px 18px;
    background: #fffaf0;
  }

  button {
    cursor: pointer;
    padding: 14px 22px;
    color: #fff9ef;
    background: #222019;
  }

  dialog {
    max-width: 420px;
    border: 0;
    border-radius: 24px;
    padding: 28px;
    color: #201911;
    background: #fff9ea;
    box-shadow: 0 28px 90px rgba(29, 22, 12, 0.36);
  }

  dialog::backdrop {
    background: rgba(28, 22, 12, 0.34);
    backdrop-filter: blur(4px);
  }

  #hello-message {
    margin: 0 0 24px;
    font-family: Georgia, Charter, serif;
    font-size: 28px;
  }

  @media (max-width: 620px) {
    .row {
      flex-direction: column;
    }
  }
`;
document.head.appendChild(style);

void main();
