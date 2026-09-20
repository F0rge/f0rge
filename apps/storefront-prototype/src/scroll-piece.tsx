import { useEffect, useRef, useState } from "react";
import { Button } from "@f0rge/ui";
import { ArrowDown, ArrowUpRight, Check, MoveHorizontal } from "lucide-react";
import type { PieceController } from "./sola-scene";

const chapters = [
  {
    name: "The silhouette",
    title: "A line worth following.",
    copy: "A low seat. A generous recline. A timber frame that draws one continuous gesture around the body.",
  },
  {
    name: "The material",
    title: "Texture does the talking.",
    copy: "Warm timber meets a softly upholstered seat. Change the finish, and the same form takes on a different character.",
  },
  {
    name: "The construction",
    title: "Nothing to hide.",
    copy: "Look a little closer. The cushions lift away to reveal the quiet structure underneath. Every part has its purpose.",
  },
];
const finishes = [
  { name: "Walnut / flax", colors: ["#795036", "#d8c9ae"] },
  { name: "Oak / oxblood", colors: ["#ba9162", "#64313b"] },
  { name: "Ebony / ochre", colors: ["#35302d", "#c1a158"] },
];

export function ScrollPiece({ onExplore }: { onExplore: () => void }) {
  const section = useRef<HTMLElement>(null);
  const host = useRef<HTMLDivElement>(null);
  const controller = useRef<PieceController | null>(null);
  const progressRef = useRef(0);
  const finishRef = useRef(0);
  const [progress, setProgress] = useState(0);
  const [finish, setFinish] = useState(0);
  const [status, setStatus] = useState<"loading" | "ready" | "fallback">(
    "loading",
  );
  const [reducedMotion, setReducedMotion] = useState(false);
  const [motionPaused, setMotionPaused] = useState(false);
  const staticMode = reducedMotion || motionPaused;
  const chapter = Math.min(2, Math.floor(progress * 3));

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    const element = section.current;
    const container = host.current;
    if (!element || !container) return;
    let stopped = false;
    let started = false;
    const observer = new IntersectionObserver(
      async (entries) => {
        if (!entries.some((entry) => entry.isIntersecting) || started) return;
        started = true;
        observer.disconnect();
        try {
          const { createSolaScene } = await import("./sola-scene");
          if (stopped) return;
          controller.current = createSolaScene(container, () =>
            setStatus("fallback"),
          );
          controller.current.setProgress(progressRef.current);
          controller.current.setFinish(finishRef.current);
          setStatus("ready");
        } catch {
          if (!stopped) setStatus("fallback");
        }
      },
      { rootMargin: "400px" },
    );
    observer.observe(element);
    return () => {
      stopped = true;
      observer.disconnect();
      controller.current?.dispose();
      controller.current = null;
    };
  }, []);

  useEffect(() => {
    if (staticMode) return;
    let frame = 0;
    const update = () => {
      frame = 0;
      const element = section.current;
      if (!element) return;
      const rect = element.getBoundingClientRect();
      const next = Math.max(
        0,
        Math.min(1, -rect.top / Math.max(1, rect.height - window.innerHeight)),
      );
      if (Math.abs(next - progressRef.current) < 0.0005) return;
      progressRef.current = next;
      setProgress(next);
      controller.current?.setProgress(next);
    };
    const requestUpdate = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    window.addEventListener("scroll", requestUpdate, { passive: true });
    window.addEventListener("resize", requestUpdate);
    update();
    return () => {
      window.removeEventListener("scroll", requestUpdate);
      window.removeEventListener("resize", requestUpdate);
      cancelAnimationFrame(frame);
    };
  }, [staticMode]);

  const chooseProgress = (next: number) => {
    if (!staticMode && section.current) {
      const element = section.current;
      window.scrollTo({
        top:
          window.scrollY +
          element.getBoundingClientRect().top +
          next * (element.offsetHeight - window.innerHeight),
        behavior: "instant",
      });
    }
    progressRef.current = next;
    setProgress(next);
    controller.current?.setProgress(next);
  };
  const chooseFinish = (index: number) => {
    finishRef.current = index;
    setFinish(index);
    controller.current?.setFinish(index);
  };

  return (
    <section
      id="sola-study"
      ref={section}
      className={`piece-scroll ${staticMode ? "piece-reduced-motion" : ""}`}
      aria-label="Sola chair, an interactive study in form"
    >
      <div className="piece-stage">
        <div className="piece-topline">
          <span>IN THE ROUND / OBJECT STUDY 004</span>
          <div className="piece-top-actions">
            <Button
              className="piece-motion"
              aria-pressed={staticMode}
              disabled={reducedMotion}
              onClick={() => {
                const top =
                  window.scrollY +
                  (section.current?.getBoundingClientRect().top || 0);
                setMotionPaused(!motionPaused);
                requestAnimationFrame(() =>
                  window.scrollTo({ top, behavior: "instant" }),
                );
              }}
            >
              {staticMode ? "Motion off" : "Pause motion"}
            </Button>
            <a href="#collection">
              Skip study <ArrowDown size={13} />
            </a>
          </div>
        </div>
        <div className="piece-intro">
          <span className="eyebrow">MEET SOLA</span>
          <h2>
            Good from
            <br />
            <em>every angle.</em>
          </h2>
          <span className="piece-scroll-cue">
            <ArrowDown size={13} />
            {staticMode ? "Choose a view below" : "Scroll slowly. Look closer."}
          </span>
        </div>
        <span className="piece-big-type" aria-hidden="true">
          SOLA
        </span>
        <div
          className="piece-canvas-host"
          ref={host}
          role="img"
          aria-label={`Three-dimensional Sola lounge chair in ${finishes[finish].name}. ${chapters[chapter].name}.`}
        >
          {status !== "ready" && (
            <svg
              className="piece-fallback"
              viewBox="0 0 600 600"
              aria-hidden="true"
            >
              <g
                fill="none"
                stroke="currentColor"
                strokeWidth="6"
                strokeLinejoin="round"
              >
                <path d="m180 390-35 125m265-135 35 130M190 185l-40 300m263-276 29 277M185 303l-53 60 278 20 50-48z" />
                <path d="m181 177 201 26 13 122-231-28z" fill="#d7c5ad" />
                <path d="m150 330 234 20 38 43-273-19z" fill="#d7c5ad" />
                <path d="m142 299 235 25m-229-23 34-124m208 148 18-113" />
              </g>
            </svg>
          )}
        </div>
        <div className="piece-caption">
          <span className="eyebrow">
            0{chapter + 1} / {chapters[chapter].name}
          </span>
          <h3>{chapters[chapter].title}</h3>
          <p>{chapters[chapter].copy}</p>
        </div>
        <div className="piece-finishes">
          <span className="eyebrow">A CHANGE OF CHARACTER</span>
          <div className="piece-swatches">
            {finishes.map((item, index) => (
              <Button
                key={item.name}
                className={`piece-swatch ${finish === index ? "selected" : ""}`}
                aria-label={item.name}
                aria-pressed={finish === index}
                onClick={() => chooseFinish(index)}
                style={{
                  background: `linear-gradient(135deg, ${item.colors[0]} 50%, ${item.colors[1]} 50%)`,
                }}
              >
                {finish === index && <Check size={15} />}
              </Button>
            ))}
          </div>
          <span className="piece-finish-name">{finishes[finish].name}</span>
          <Button className="text-link" onClick={onExplore}>
            Explore seating <ArrowUpRight size={15} />
          </Button>
        </div>
        <div className="piece-bottom">
          <div className="piece-chapters" aria-label="Chair study chapters">
            {chapters.map((item, index) => (
              <Button
                key={item.name}
                className={chapter === index ? "selected" : ""}
                aria-pressed={chapter === index}
                onClick={() => chooseProgress([0, 0.5, 0.92][index])}
              >
                <span>0{index + 1}</span>
                {item.name}
              </Button>
            ))}
          </div>
          <label className="piece-scrubber">
            <MoveHorizontal size={15} />
            <span className="sr-only">Rotate and explore the Sola chair</span>
            <input
              type="range"
              min="0"
              max="100"
              value={Math.round(progress * 100)}
              onChange={(event) =>
                chooseProgress(Number(event.target.value) / 100)
              }
            />
            <span>{Math.round(progress * 360)}°</span>
          </label>
        </div>
        {status === "fallback" && (
          <p className="piece-fallback-note">
            A drawn study is shown because 3D is unavailable in this browser.
          </p>
        )}
      </div>
    </section>
  );
}
