import { forwardRef, useRef, useImperativeHandle } from "react";
import ReactSignatureCanvas from "react-signature-canvas";

export interface SignatureCanvasRef {
  toDataURL: () => string;
  isEmpty: () => boolean;
  clear: () => void;
}

interface Props {
  hasError?: boolean;
  onBegin?: () => void;
}

const SignatureCanvas = forwardRef<SignatureCanvasRef, Props>(
  ({ hasError, onBegin }, ref) => {
    const innerRef = useRef<ReactSignatureCanvas>(null);

    useImperativeHandle(ref, () => ({
      toDataURL: () => innerRef.current?.toDataURL("image/png") ?? "",
      isEmpty: () => innerRef.current?.isEmpty() ?? true,
      clear: () => innerRef.current?.clear(),
    }));

    return (
      <div className="space-y-2">
        <div
          className={`overflow-hidden rounded-sm border bg-well ${
            hasError ? "border-danger" : "border-white/15 focus-within:border-copper/60"
          }`}
        >
          <ReactSignatureCanvas
            ref={innerRef}
            onBegin={onBegin}
            canvasProps={{
              className: "w-full touch-none",
              height: 140,
              style: { display: "block" },
            }}
            backgroundColor="transparent"
            penColor="rgba(255,255,255,0.85)"
          />
        </div>
        <button
          type="button"
          onClick={() => innerRef.current?.clear()}
          className="rounded-sm border border-white/20 px-3 py-1 text-xs text-white/50 transition hover:border-white/40 hover:text-white/80"
        >
          נקה
        </button>
      </div>
    );
  },
);

SignatureCanvas.displayName = "SignatureCanvas";
export default SignatureCanvas;
