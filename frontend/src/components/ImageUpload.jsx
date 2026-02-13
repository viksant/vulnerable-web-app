import { useState, useRef } from "react";
import { Upload } from "lucide-react";
import Button from "./ui/Button";

/**
 * Neo-Brutalist image upload component.
 * File input hidden behind a styled button.
 *
 * @param {object} props
 * @param {function} props.onUpload - Called with the File object.
 */
export default function ImageUpload({ onUpload }) {
  const [preview, setPreview] = useState(null);
  const fileRef = useRef(null);

  function handleFileChange(e) {
    const file = e.target.files?.[0];
    if (!file) return;

    setPreview(URL.createObjectURL(file));
    onUpload?.(file);
  }

  return (
    <div className="flex flex-col gap-4">
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        onChange={handleFileChange}
        className="hidden"
      />

      <Button
        type="button"
        variant="outline"
        onClick={() => fileRef.current?.click()}
      >
        <Upload className="mr-2 inline h-5 w-5" strokeWidth={3} />
        UPLOAD IMAGE
      </Button>

      {preview && (
        <div className="h-40 w-40 border-4 border-black shadow-neo-sm">
          <img
            src={preview}
            alt="Preview"
            className="h-full w-full object-cover"
          />
        </div>
      )}
    </div>
  );
}
