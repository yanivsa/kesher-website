export interface ContactRequest {
  kind: "contact" | "lead_magnet";
  name?: string;
  email: string;
  phone?: string;
  service?: string;
  message?: string;
  company?: string;
  startedAt: number;
}

interface ContactResponse {
  success: boolean;
  message: string;
  downloadUrl?: string;
}

export async function submitContact(
  request: ContactRequest,
): Promise<ContactResponse> {
  const response = await fetch("/api/contact", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  const result = (await response.json()) as ContactResponse;

  if (!response.ok || !result.success) {
    throw new Error(result.message || "Request failed");
  }

  return result;
}
