import { expect, test } from "@playwright/test";

/**
 * Tests for the PDF Loader API endpoint.
 *
 * Endpoint: POST /api/v1/flows/pdf-loader
 *
 * Accepts multipart/form-data with a `file` field containing a PDF.
 * Returns JSON: { text: string, page_count: number, status: "success" }
 *
 * Error cases:
 *   - Corrupted PDF  → 400 with { detail: string }
 *   - Non-PDF file   → 400 or 415 with { detail: string }
 */

const PDF_LOADER_URL = "/api/v1/flows/pdf-loader";

// ---------------------------------------------------------------------------
// Minimal valid single-page PDF builder (no external files needed)
// ---------------------------------------------------------------------------

function buildMinimalPdf(pageText: string = "Hello PDF World"): Buffer {
  const stream = `BT\n/F1 12 Tf\n72 720 Td\n(${pageText}) Tj\nET`;
  const streamBytes = Buffer.from(stream, "latin1");
  const streamLen = streamBytes.length;

  const obj1 = Buffer.from(
    "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
    "latin1"
  );
  const obj2 = Buffer.from(
    "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
    "latin1"
  );
  const obj3 = Buffer.from(
    "3 0 obj\n<< /Type /Page /Parent 2 0 R " +
      "/MediaBox [0 0 612 792] /Contents 4 0 R " +
      "/Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
    "latin1"
  );
  const obj4 = Buffer.concat([
    Buffer.from(`4 0 obj\n<< /Length ${streamLen} >>\nstream\n`, "latin1"),
    streamBytes,
    Buffer.from("\nendstream\nendobj\n", "latin1"),
  ]);
  const obj5 = Buffer.from(
    "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    "latin1"
  );

  const header = Buffer.from("%PDF-1.4\n", "latin1");
  const objects = [obj1, obj2, obj3, obj4, obj5];

  let body = header;
  const offsets: number[] = [];
  for (const obj of objects) {
    offsets.push(body.length);
    body = Buffer.concat([body, obj]);
  }

  const xrefOffset = body.length;
  let xref = `xref\n0 ${objects.length + 1}\n`;
  xref += "0000000000 65535 f \n";
  for (const off of offsets) {
    xref += String(off).padStart(10, "0") + " 00000 n \n";
  }

  const trailer =
    `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\n` +
    `startxref\n${xrefOffset}\n%%EOF`;

  return Buffer.concat([
    body,
    Buffer.from(xref, "latin1"),
    Buffer.from(trailer, "latin1"),
  ]);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("PDF Loader API endpoint", () => {
  test("should upload a PDF and extract text content from all pages", async ({
    request,
  }) => {
    const pdfBytes = buildMinimalPdf("Hello PDF World");

    const resp = await request.post(PDF_LOADER_URL, {
      multipart: {
        file: {
          name: "test-doc.pdf",
          mimeType: "application/pdf",
          buffer: pdfBytes,
        },
      },
    });

    expect(resp.ok()).toBeTruthy();
    expect(resp.status()).toBe(200);

    const body = await resp.json();

    expect(body).toHaveProperty("text");
    expect(body).toHaveProperty("page_count");
    expect(body).toHaveProperty("status");

    expect(typeof body.text).toBe("string");
    expect(typeof body.page_count).toBe("number");
    expect(body.status).toBe("success");
    expect(body.page_count).toBeGreaterThanOrEqual(1);
    expect(body.text).toContain("Hello PDF World");
  });

  test("should return page_count matching the number of pages in the PDF", async ({
    request,
  }) => {
    const pdfBytes = buildMinimalPdf("Page one content");

    const resp = await request.post(PDF_LOADER_URL, {
      multipart: {
        file: {
          name: "single-page.pdf",
          mimeType: "application/pdf",
          buffer: pdfBytes,
        },
      },
    });

    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body.page_count).toBe(1);
    expect(body.status).toBe("success");
  });

  test("should return 400 for a corrupted PDF file", async ({ request }) => {
    // Starts with %PDF magic but is otherwise garbage
    const corruptedPdf = Buffer.from(
      "%PDF-1.4\nThis is not a valid PDF - corrupted content!!!",
      "latin1"
    );

    const resp = await request.post(PDF_LOADER_URL, {
      multipart: {
        file: {
          name: "corrupted.pdf",
          mimeType: "application/pdf",
          buffer: corruptedPdf,
        },
      },
    });

    expect(resp.status()).toBe(400);
    const body = await resp.json();
    expect(body).toHaveProperty("detail");
    expect(typeof body.detail).toBe("string");
    expect(body.detail.length).toBeGreaterThan(0);
  });

  test("should return 400 or 415 for a non-PDF file", async ({ request }) => {
    const textContent = Buffer.from(
      "This is a plain text file, not a PDF.",
      "utf-8"
    );

    const resp = await request.post(PDF_LOADER_URL, {
      multipart: {
        file: {
          name: "document.txt",
          mimeType: "text/plain",
          buffer: textContent,
        },
      },
    });

    expect([400, 415]).toContain(resp.status());
    const body = await resp.json();
    expect(body).toHaveProperty("detail");
  });

  test("should return 400 or 415 for a JPEG file uploaded as PDF", async ({
    request,
  }) => {
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

    expect([400, 415]).toContain(resp.status());
    const body = await resp.json();
    expect(body).toHaveProperty("detail");
  });

  test("should return status field as 'success' on valid PDF", async ({
    request,
  }) => {
    const pdfBytes = buildMinimalPdf("Status check content");

    const resp = await request.post(PDF_LOADER_URL, {
      multipart: {
        file: {
          name: "status-check.pdf",
          mimeType: "application/pdf",
          buffer: pdfBytes,
        },
      },
    });

    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body.status).toBe("success");
  });

  test("should return text as a string (even if empty) for a valid PDF", async ({
    request,
  }) => {
    const pdfBytes = buildMinimalPdf("Some extractable text");

    const resp = await request.post(PDF_LOADER_URL, {
      multipart: {
        file: {
          name: "text-check.pdf",
          mimeType: "application/pdf",
          buffer: pdfBytes,
        },
      },
    });

    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(typeof body.text).toBe("string");
  });
});
