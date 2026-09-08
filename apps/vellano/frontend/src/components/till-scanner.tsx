"use client";

import { Button, InlineNotification, Modal, Stack, TextInput } from "@carbon/react";
import { Flash } from "@carbon/icons-react";
import { useEffect, useRef, useState } from "react";

import {
  SAME_CODE_COOLDOWN_MS,
  createBarcodeDetector,
  type BarcodeDetectorLike,
} from "@/lib/barcode-scan";

const CAMERA_HELP = "Camera needs HTTPS and permission. You can type the barcode instead.";

type TillScannerProps = {
  onClose: () => void;
  onDetect: (rawValue: string) => void;
  onTypeIn: (rawValue: string) => void;
};

export function TillScanner({ onClose, onDetect, onTypeIn }: TillScannerProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const detectorRef = useRef<BarcodeDetectorLike | null>(null);
  const lastCodeRef = useRef("");
  const lastAtRef = useRef(0);
  const onDetectRef = useRef(onDetect);

  useEffect(() => {
    onDetectRef.current = onDetect;
  }, [onDetect]);

  const [typed, setTyped] = useState("");
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [torchOn, setTorchOn] = useState(false);
  const [torchAvailable, setTorchAvailable] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let raf = 0;
    let detecting = false;

    function stopTracks() {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      const video = videoRef.current;
      if (video) {
        video.srcObject = null;
      }
    }

    async function start() {
      try {
        detectorRef.current = await createBarcodeDetector();
      } catch {
        if (!cancelled) {
          setCameraError(CAMERA_HELP);
        }
        return;
      }

      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "environment" },
          audio: false,
        });
      } catch {
        try {
          stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        } catch {
          if (!cancelled) {
            setCameraError(CAMERA_HELP);
          }
          return;
        }
      }

      if (cancelled) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }

      streamRef.current = stream;
      const video = videoRef.current;
      if (video) {
        video.srcObject = stream;
        try {
          await video.play();
        } catch {
          // Autoplay can fail after permission; type-in still works.
        }
      }

      const track = stream.getVideoTracks()[0];
      const caps = track?.getCapabilities?.() as { torch?: boolean } | undefined;
      if (!cancelled && caps?.torch) {
        setTorchAvailable(true);
      }

      const tick = () => {
        if (cancelled) {
          return;
        }
        const liveVideo = videoRef.current;
        const detector = detectorRef.current;
        if (liveVideo && detector && liveVideo.readyState >= 2 && !detecting) {
          detecting = true;
          void detector
            .detect(liveVideo)
            .then((codes) => {
              const raw = codes[0]?.rawValue?.trim() ?? "";
              if (!raw) {
                return;
              }
              const now = Date.now();
              if (raw === lastCodeRef.current && now - lastAtRef.current < SAME_CODE_COOLDOWN_MS) {
                return;
              }
              lastCodeRef.current = raw;
              lastAtRef.current = now;
              onDetectRef.current(raw);
            })
            .catch(() => {
              /* skip a bad frame */
            })
            .finally(() => {
              detecting = false;
            });
        }
        raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    }

    void start();

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      stopTracks();
    };
  }, []);

  async function toggleTorch() {
    const track = streamRef.current?.getVideoTracks()[0];
    if (!track) {
      return;
    }
    const next = !torchOn;
    try {
      await track.applyConstraints({
        advanced: [{ torch: next } as MediaTrackConstraintSet],
      });
      setTorchOn(next);
    } catch {
      setTorchAvailable(false);
    }
  }

  function submitTyped() {
    const value = typed.trim();
    if (!value) {
      return;
    }
    onTypeIn(value);
    setTyped("");
  }

  return (
    <Modal
      open
      modalHeading="Scan barcode"
      primaryButtonText="Close"
      onRequestClose={onClose}
      onRequestSubmit={onClose}
      size="md"
    >
      <Stack gap={5}>
        <p className="cds--type-body-01">{CAMERA_HELP}</p>
        {cameraError ? (
          <InlineNotification
            kind="warning"
            title="Camera unavailable"
            subtitle={cameraError}
            hideCloseButton
            lowContrast
          />
        ) : null}
        <div className="vellano-till-scanner__frame">
          <video
            ref={videoRef}
            className="vellano-till-scanner__video"
            muted
            playsInline
            autoPlay
          />
        </div>
        {torchAvailable ? (
          <Button kind="tertiary" renderIcon={Flash} onClick={() => void toggleTorch()}>
            {torchOn ? "Torch off" : "Torch on"}
          </Button>
        ) : null}
        <TextInput
          id="till-scanner-type"
          labelText="Type or paste barcode"
          value={typed}
          onChange={(event) => setTyped(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              submitTyped();
            }
          }}
        />
      </Stack>
    </Modal>
  );
}
