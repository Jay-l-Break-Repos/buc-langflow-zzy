import { expect, test } from "@playwright/test";

/**
 * PDF Loader API endpoint tests.
 *
 * Endpoint: POST /api/v1/flows/pdf-loader
 * Accepts:  multipart/form-data with a `file` field (PDF)
 * Returns:  { text: string, page_count: number, status: "success" }
 */

// Base URL: use PLAYWRIGHT_BASE_URL env var if set (evaluation environment),
// otherwise fall back to the Docker default port 9090.
const BASE_URL =
  process.env.PLAYWRIGHT_BASE_URL ||
  process.env.API_BASE_URL ||
  "http://localhost:9090";

const PDF_LOADER_URL = `${BASE_URL}/api/v1/flows/pdf-loader`;

const pdfContent = `%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length 44>>stream
BT /F1 12 Tf 100 700 Td (Hello World) Tj ET
endstream endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
xref
0 6
trailer<</Size 6/Root 1 0 R>>
startxref
9
%%EOF`;

test.describe("PDF Loader", () => {
  test("should upload a PDF and extract text content from all pages", async ({
    request,
  }) => {
    const resp = await request.post(PDF_LOADER_URL, {
      multipart: {
        file: {
          name: "test-doc.pdf",
          mimeType: "application/pdf",
          buffer: Buffer.from(pdfContent),
        },
      },
    });
    console.log("Response status:", resp.status());
    const body = await resp.text();
    console.log("Response body:", body);
    expect(resp.ok()).toBeTruthy();
    const result = JSON.parse(body);
    expect(result.text).toBeDefined();
    expect(result.text.length).toBeGreaterThan(0);
    expect(result.page_count).toBeDefined();
    expect(result.page_count).toBeGreaterThan(0);
    expect(result.status).toBe("success");
  });

  test("should return page_count as a number", async ({ request }) => {
    const resp = await request.post(PDF_LOADER_URL, {
      multipart: {
        file: {
          name: "test-doc.pdf",
          mimeType: "application/pdf",
          buffer: Buffer.from(pdfContent),
        },
      },
    });
    console.log("Response status:", resp.status());
    expect(resp.ok()).toBeTruthy();
    const result = await resp.json();
    expect(typeof result.page_count).toBe("number");
  });

  test("should return status as success", async ({ request }) => {
    const resp = await request.post(PDF_LOADER_URL, {
      multipart: {
        file: {
          name: "test-doc.pdf",
          mimeType: "application/pdf",
          buffer: Buffer.from(pdfContent),
        },
      },
    });
    expect(resp.ok()).toBeTruthy();
    const result = await resp.json();
    expect(result.status).toBe("success");
  });

  test("should return 400 for corrupted PDF", async ({ request }) => {
    const resp = await request.post(PDF_LOADER_URL, {
      multipart: {
        file: {
          name: "corrupted.pdf",
          mimeType: "application/pdf",
          buffer: Buffer.from("%PDF-1.4\ncorrupted content"),
        },
      },
    });
    console.log("Corrupted PDF status:", resp.status());
    expect(resp.status()).toBe(400);
    const result = await resp.json();
    expect(result.detail).toBeDefined();
  });

  test("should return 400 or 415 for non-PDF file", async ({ request }) => {
    const resp = await request.post(PDF_LOADER_URL, {
      multipart: {
        file: {
          name: "document.txt",
          mimeType: "text/plain",
          buffer: Buffer.from("This is not a PDF file"),
        },
      },
    });
    console.log("Non-PDF status:", resp.status());
    expect([400, 415]).toContain(resp.status());
    const result = await resp.json();
    expect(result.detail).toBeDefined();
  });

  test("should return text field as string", async ({ request }) => {
    const resp = await request.post(PDF_LOADER_URL, {
      multipart: {
        file: {
          name: "test-doc.pdf",
          mimeType: "application/pdf",
          buffer: Buffer.from(pdfContent),
        },
      },
    });
    expect(resp.ok()).toBeTruthy();
    const result = await resp.json();
    expect(typeof result.text).toBe("string");
  });

  test("should handle PDF with Hello World text", async ({ request }) => {
    const resp = await request.post(PDF_LOADER_URL, {
      multipart: {
        file: {
          name: "test-doc.pdf",
          mimeType: "application/pdf",
          buffer: Buffer.from(pdfContent),
        },
      },
    });
    expect(resp.ok()).toBeTruthy();
    const result = await resp.json();
    expect(result.text).toContain("Hello World");
  });

  test("should return 400 or 415 for JPEG file", async ({ request }) => {
    const jpegBytes = Buffer.from([
      0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46,
    ]);
    const resp = await request.post(PDF_LOADER_URL, {
      multipart: {
        file: {
          name: "image.jpg",
          mimeType: "image/jpeg",
          buffer: jpegBytes,
        },
      },
    });
    console.log("JPEG status:", resp.status());
    expect([400, 415]).toContain(resp.status());
    const result = await resp.json();
    expect(result.detail).toBeDefined();
  });
});
