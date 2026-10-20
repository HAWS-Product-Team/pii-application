import { useCallback, useEffect, useState } from "react";
import { useDropzone, type FileRejection } from "react-dropzone";
import folderLogo from "../assets/folder.svg";
import { createUploadSession, uploadPdf } from "../api";

interface UploadFileProps {
    isImporting: boolean;
    onImportComplete: () => void;
}

const MAX_FILES = 20;
const MIN_FILE_SIZE = 1024 * 1024;
const MAX_FILE_SIZE = 15 * 1024 * 1024;
const MAX_TOTAL_SIZE = 4 * 1024 * 1024 * 1024;

export default function UploadFile({
    isImporting,
    onImportComplete,
}: UploadFileProps) {
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
    const [error, setError] = useState("");
    const [status, setStatus] = useState("");
    const [isUploading, setIsUploading] = useState(false);

    const onDrop = useCallback(
        (acceptedFiles: File[], rejections: FileRejection[]) => {
            setError("");
            setStatus("");

            if (rejections.length > 0) {
                setError(
                    rejections
                        .map(({ file, errors }) =>
                            `${file.name}: ${errors.map((item) => item.message).join(", ")}`
                        )
                        .join(" ")
                );
            }

            setSelectedFiles((previousFiles) => {
                const unique = new Map<string, File>();

                for (const file of [...previousFiles, ...acceptedFiles]) {
                    unique.set(file.name.toLowerCase(), file);
                }

                const nextFiles = Array.from(unique.values());

                if (nextFiles.length > MAX_FILES) {
                    setError(`Select no more than ${MAX_FILES} PDF files.`);
                    return previousFiles;
                }

                if (
                    nextFiles.reduce((total, file) => total + file.size, 0) >
                    MAX_TOTAL_SIZE
                ) {
                    setError("The combined file size cannot exceed 4 GiB.");
                    return previousFiles;
                }

                return nextFiles;
            });
        },
        []
    );

    const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
        accept: { "application/pdf": [".pdf"] },
        multiple: true,
        maxFiles: MAX_FILES,
        minSize: MIN_FILE_SIZE,
        maxSize: MAX_FILE_SIZE,
        onDrop,
        noClick: true,
        noKeyboard: true,
        disabled: isUploading,
    });

    useEffect(() => {
        if (isImporting && !isUploading) {
            open();
            onImportComplete();
        }
    }, [isImporting, isUploading, open, onImportComplete]);

    const removeFile = (filename: string) => {
        setSelectedFiles((files) =>
            files.filter((file) => file.name !== filename)
        );
    };

    const formatSize = (bytes: number) =>
        `${(bytes / (1024 * 1024)).toFixed(2)} MB`;

    const handleUpload = async () => {
        if (selectedFiles.length === 0) {
            setError("Select at least one PDF statement first.");
            return;
        }

        setIsUploading(true);
        setError("");
        setStatus("Requesting secure upload URLs...");

        try {
            const session = await createUploadSession(
                selectedFiles.map((file) => ({
                    filename: file.name,
                    fileSizeBytes: file.size,
                }))
            );

            if (session.uploads.length !== selectedFiles.length) {
                throw new Error(
                    "The API returned a different number of upload URLs than selected files."
                );
            }

            for (let index = 0; index < session.uploads.length; index++) {
                const upload = session.uploads[index];
                const file = selectedFiles.find(
                    (candidate) => candidate.name === upload.filename
                );

                if (!file) {
                    throw new Error(
                        `Could not match the upload URL to ${upload.filename}.`
                    );
                }

                setStatus(
                    `Uploading statement ${index + 1} of ${session.uploads.length}: ${file.name}`
                );

                await uploadPdf(upload.uploadUrl, file);
            }

            setStatus(
                `All ${session.expectedFileCount} statement(s) uploaded successfully.`
            );
        } catch (uploadError) {
            setError(
                uploadError instanceof Error
                    ? uploadError.message
                    : "An unexpected upload error occurred."
            );
            setStatus("");
        } finally {
            setIsUploading(false);
        }
    };

    return (
        <div className="my-8">
            <div
                {...getRootProps()}
                className="flex flex-col items-center gap-3 rounded-lg p-6"
            >
                <input {...getInputProps()} />
                <img src={folderLogo} alt="" />

                <div className="text-xl font-bold text-center">
                    {isDragActive
                        ? "Drop your PDF statements here"
                        : "Drag and drop PDF statements here"}
                </div>

                <p className="text-gray-700 text-center">
                    Select up to 20 PDFs. Each file must be between 1 MB and
                    15 MB.
                </p>

                <button
                    type="button"
                    onClick={open}
                    disabled={isUploading}
                    className="bg-[#33B4A8] rounded-lg px-6 py-2 text-white font-bold disabled:opacity-50"
                >
                    Browse PDFs
                </button>
            </div>

            {error && (
                <p role="alert" className="mt-3 text-red-700">
                    {error}
                </p>
            )}

            {status && (
                <p role="status" aria-live="polite" className="mt-3 text-center">
                    {status}
                </p>
            )}

            {selectedFiles.length > 0 && (
                <div className="mt-6 text-left">
                    <div className="flex flex-wrap justify-between gap-3">
                        <h2 className="font-bold text-lg">
                            Selected statements ({selectedFiles.length})
                        </h2>

                        <button
                            type="button"
                            disabled={isUploading}
                            onClick={handleUpload}
                            className="bg-[#33B4A8] rounded-lg px-6 py-2 text-white font-bold disabled:opacity-50"
                        >
                            {isUploading ? "Uploading..." : "Upload Statements"}
                        </button>
                    </div>

                    <ul className="mt-3 space-y-2">
                        {selectedFiles.map((file) => (
                            <li
                                key={`${file.name}-${file.lastModified}`}
                                className="flex flex-wrap items-center justify-between gap-2 rounded border p-3"
                            >
                                <span className="break-all">{file.name}</span>
                                <span className="text-gray-600">
                                    {formatSize(file.size)}
                                </span>
                                <button
                                    type="button"
                                    disabled={isUploading}
                                    onClick={() => removeFile(file.name)}
                                    className="text-red-700 underline disabled:opacity-50"
                                >
                                    Remove
                                </button>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
}
