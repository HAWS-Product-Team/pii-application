const API_ROOT = "https://5m782q7f45.execute-api.us-east-1.amazonaws.com/dev/";

interface ApiLink {
    href: string;
    rel: string;
}

interface RootResponse {
    links: ApiLink[];
}

export interface UploadDescriptor {
    filename: string;
    fileSizeBytes: number;
}

export interface PresignedUpload {
    filename: string;
    key: string;
    uploadUrl: string;
}

export interface UploadSession {
    ticketId: string;
    secret: string;
    uploadPrefix: string;
    uploads: PresignedUpload[];
    expectedFileCount: number;
    expiresInSeconds: number;
}

async function readJson<T>(response: Response): Promise<T> {
    const data = await response.json().catch(() => null);

    if (!response.ok) {
        const message =
            data && typeof data.error === "string"
                ? data.error
                : `Request failed with status ${response.status}`;

        throw new Error(message);
    }

    return data as T;
}

export async function getUploadEndpoint(): Promise<string> {
    const response = await fetch(API_ROOT);
    const root = await readJson<RootResponse>(response);

    const uploadLink = root.links?.find((link) => link.rel === "upload");

    if (!uploadLink?.href) {
        throw new Error("The API root did not provide an upload link.");
    }

    return new URL(uploadLink.href, API_ROOT).toString();
}

export async function createUploadSession(
    files: UploadDescriptor[]
): Promise<UploadSession> {
    const endpoint = await getUploadEndpoint();

    const response = await fetch(endpoint, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ files }),
    });

    return readJson<UploadSession>(response);
}

export async function uploadPdf(
    uploadUrl: string,
    file: File
): Promise<void> {
    const response = await fetch(uploadUrl, {
        method: "PUT",
        headers: {
            "Content-Type": "application/pdf",
        },
        body: file,
    });

    if (!response.ok) {
        throw new Error(
            `Uploading ${file.name} failed with status ${response.status}`
        );
    }
}
