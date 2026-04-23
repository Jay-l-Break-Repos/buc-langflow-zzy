import { expect, test } from "@playwright/test";

/**
 * Tests for the PDF Loader API endpoint.
 *
 * Endpoint: POST /api/v1/flows/pdf-loader
 *
 * The endpoint accepts a multipart/form-data upload with a single `file`
 * field containing a PDF and returns JSON:
 *   { text: string, page_count: number, status: "success" }
 *
 * Error cases:
 *   - Corrupted PDF  → 400 with error detail
 *   - Non-PDF file   → 400 or 415 with error detail
 */

const PDF_LOADER_URL = "/api/v1/flows/pdf-loader";

// ---------------------------------------------------------------------------
// Minimal valid single-page PDF (hand-crafted, contains "Hello PDF World")
// ---------------------------------------------------------------------------
function buildMinimalPdf(text: string = "Hello PDF World"): Buffer {
  // We build a minimal but spec-compliant PDF so we don't need a file on disk.
  const stream =
    `BT\n/F1 12 Tf\n72 720 Td\n(${text}) Tj\nET`;
  const streamLen = Buffer.byteLength(stream, "latin1");

  const objects: string[] = [];

  // Object 1 – Catalog
  objects.push("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj");
  // Object 2 – Pages
  objects.push(
    "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj"
  );
  // Object 3 – Page
  objects.push(
    "3 0 obj\n<< /Type /Page /Parent 2 0 R " +
      "/MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj"
  );
  // Object 4 – Content stream
  objects.push(
    `4 0 obj\n<< /Length ${streamLen} >>\nstream\n${stream}\nendstream\nendobj`
  );
  // Object 5 – Font
  objects.push(
    "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj"
  );

  // Build the body
  const header = "%PDF-1.4\n";
  let body = header;
  const offsets: number[] = [];
  for (const obj of objects) {
    offsets.push(Buffer.byteLength(body, "latin1"));
    body += obj + "\n";
  }

  // Cross-reference table
  const xrefOffset = Buffer.byteLength(body, "latin1");
  let xref = `xref\n0 ${objects.length + 1}\n`;
  xref += "0000000000 65535 f \n";
  for (const off of offsets) {
    xref += String(off).padStart(10, "0") + " 00000 n \n";
  }

  const trailer =
    `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\n` +
    `startxref\n${xrefOffset}\n%%EOF`;

  return Buffer.from(body + xref + trailer, "latin1");
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("PDF Loader API endpoint", () => {
  test("should upload a PDF and extract text content from all pages", async ({
    request,
  }) => {
    const pdfBytes = buildMinimalPdf("Hello PDF World");

    const response = await request.post(PDF_LOADER_URL, {
      multipart: {
        file: {
          name: "test.pdf",
          mimeType: "application/pdf",
          buffer: pdfBytes,
        },
      },
    });

    expect(response.status()).toBe(200);

    const body = await response.json();

    // Required fields
    expect(body).toHaveProperty("text");
    expect(body).toHaveProperty("page_count");
    expect(body).toHaveProperty("status");

    // Type checks
    expect(typeof body.text).toBe("string");
    expect(typeof body.page_count).toBe("number");
    expect(body.status).toBe("success");

    // Content checks
    expect(body.page_count).toBeGreaterThanOrEqual(1);
    // The extracted text should contain our test string
    expect(body.text).toContain("Hello PDF World");
  });

  test("should return page_count matching the number of pages in the PDF", async ({
    request,
  }) => {
    const pdfBytes = buildMinimalPdf("Page one content");

    const response = await request.post(PDF_LOADER_URL, {
      multipart: {
        file: {
          name: "single_page.pdf",
          mimeType: "application/pdf",
          buffer: pdfBytes,
        },
      },
    });

    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body.page_count).toBe(1);
    expect(body.status).toBe("success");
  });

  test("should return 400 for a corrupted PDF file", async ({ request }) => {
    // Starts with %PDF magic but is otherwise garbage
    const corruptedPdf = Buffer.from(
      "%PDF-1.4\nThis is not a valid PDF file at all - corrupted content!!!",
      "latin1"
    );

    const response = await request.post(PDF_LOADER_URL, {
      multipart: {
        file: {
          name: "corrupted.pdf",
          mimeType: "application/pdf",
          buffer: corruptedPdf,
        },
      },
    });

    expect(response.status()).toBe(400);
    const body = await response.json();
    expect(body).toHaveProperty("detail");
    expect(typeof body.detail).toBe("string");
    expect(body.detail.length).toBeGreaterThan(0);
  });

  test("should return 400 or 415 for a non-PDF file", async ({ request }) => {
    const textContent = Buffer.from(
      "This is a plain text file, not a PDF.",
      "utf-8"
    );

    const response = await request.post(PDF_LOADER_URL, {
      multipart: {
        file: {
          name: "document.txt",
          mimeType: "text/plain",
          buffer: textContent,
        },
      },
    });

    expect([400, 415]).toContain(response.status());
    const body = await response.json();
    expect(body).toHaveProperty("detail");
  });

  test("should return 400 or 415 for a JPEG file uploaded as PDF", async ({
    request,
  }) => {
    // Minimal JPEG magic bytes followed by garbage
    const jpegBytes = Buffer.from([
      0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46,
    ]);

    const response = await request.post(PDF_LOADER_URL, {
      multipart: {
        file: {
          name: "image.jpg",
          mimeType: "image/jpeg",
          buffer: jpegBytes,
        },
      },
    });

    expect([400, 415]).toContain(response.status());
    const body = await response.json();
    expect(body).toHaveProperty("detail");
  });

  test("should return status field as 'success' on valid PDF", async ({
    request,
  }) => {
    const pdfBytes = buildMinimalPdf("Status check");

    const response = await request.post(PDF_LOADER_URL, {
      multipart: {
        file: {
          name: "status_check.pdf",
          mimeType: "application/pdf",
          buffer: pdfBytes,
        },
      },
    });

    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body.status).toBe("success");
  });
});
