import { useDropzone } from "react-dropzone";
import { useEffect } from "react";
import folderLogo from "../assets/folder.svg"

interface UploadFileProps {
    isImporting: boolean,
    onImportComplete: () => void;
}
export default function UploadFile({ isImporting, onImportComplete }: UploadFileProps) {
    const onDrop = async (files: File[]) => {
        try {
            const formData = new FormData();
            formData.append('file', files[0]);
            const res = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            if (!res.ok) {
                throw Error('Unable to upload file');
            }
        } catch (err) {
            console.error(err);
        }
    };

    const { getRootProps, getInputProps, isDragActive, open} = useDropzone({
        accept: {'text/csv': ['.csv']},
        multiple: false,
        onDrop
    });

    useEffect(() => {
        if (isImporting) {
            open();
            onImportComplete();
        }

    }, [isImporting]);

    return (
        <div {...getRootProps() } className="flex flex-col my-8">
            <div className="flex justify-center space-x-4">

            
            <img src={folderLogo} alt='folder'/>
            <input {...getInputProps() }/>
                <div className="py-4 font-bold text-2xl">
                { isDragActive ? <p>Drop the file here</p> : <p>Drag & drop CSV file here</p>}
                </div>
            </div>
            <div>
                <p className="text-gray-800">
                    or use the import button above
                </p>
            </div>
            
        </div>
    );
}