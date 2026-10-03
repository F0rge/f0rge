"use client";

import { useCallback, useEffect, useRef, useState, type CSSProperties } from "react";
import Link from "next/link";
import {
  publishStudyEvent,
  SOLA_STUDY_ID,
  type StudyProgressMilestone,
} from "./study-events";
import type { SolaController } from "./sola-scene";
import "./study.css";

const chapters = [
  {
    name: "The silhouette",
    title: "A line worth following.",
    copy: "A low seat, a generous recline and a frame traced as one gesture.",
  },
  {
    name: "The material",
    title: "Texture shifts the mood.",
    copy: "Illustrative timber and fabric palettes explore character; they are not product finish options.",
  },
  {
    name: "The construction",
    title: "Structure, made visible.",
    copy: "Lift the study cushions to reveal the frame, a procedural detail rather than a manufacturing claim.",
  },
] as const;

const finishes = [
  { name: "Walnut / flax", wood: "#997453", fabric: "#e4d3b5" },
  { name: "Oak / oxblood", wood: "#d0ae7a", fabric: "#79414b" },
  { name: "Ebony / ochre", wood: "#4e4843", fabric: "#c8a04f" },
] as const;

const milestones: StudyProgressMilestone[] = [25, 50, 75, 100];
const chapterPositions = [0.08, 0.5, 0.92] as const;

type RenderState = "idle" | "loading" | "ready" | "fallback";
type NavigatorHints = Navigator & {
  deviceMemory?: number;
  connection?: { saveData?: boolean };
};

function isConstrainedDevice(): boolean {
  const hints = navigator as NavigatorHints;
  return Boolean(
    hints.connection?.saveData ||
      (hints.deviceMemory != null && hints.deviceMemory <= 2) ||
      (navigator.hardwareConcurrency > 0 && navigator.hardwareConcurrency <= 2),
  );
}

function sectionIsVisible(section: HTMLElement): boolean {
  const rect = section.getBoundingClientRect();
  return rect.bottom > 0 && rect.top < window.innerHeight;
}

export function InteractiveStudy() {
  const sectionRef = useRef<HTMLElement>(null);
  const hostRef = useRef<HTMLDivElement>(null);
  const controllerRef = useRef<SolaController | null>(null);
  const progressRef = useRef(0);
  const finishRef = useRef(0);
  const activeRef = useRef(false);
  const enteredRef = useRef(false);
  const finishSentRef = useRef(false);
  const sentMilestonesRef = useRef(new Set<StudyProgressMilestone>());
  const [progress, setProgress] = useState(0);
  const [finish, setFinish] = useState(0);
  const [chapter, setChapter] = useState(0);
  const [renderState, setRenderState] = useState<RenderState>("idle");
  const [reducedMotion, setReducedMotion] = useState(false);
  const [motionPreferenceReady, setMotionPreferenceReady] = useState(false);
  const [constrained, setConstrained] = useState(false);
  const [motionPaused, setMotionPaused] = useState(false);
  const staticMode = reducedMotion || motionPaused;
  const canLoadScene = motionPreferenceReady && !reducedMotion && !constrained;
  const currentFinish = finishes[finish];
  const currentChapter = chapters[chapter];

  const commitProgress = useCallback((value: number) => {
    const next = Math.max(0, Math.min(1, value));
    if (Math.abs(next - progressRef.current) < 0.0005) return;
    progressRef.current = next;
    setProgress(next);
    const nextChapter = Math.min(2, Math.floor(next * 3));
    setChapter(nextChapter);
    controllerRef.current?.setProgress(next);

    if (!enteredRef.current) return;
    for (const milestone of milestones) {
      if (next >= milestone / 100 && !sentMilestonesRef.current.has(milestone)) {
        sentMilestonesRef.current.add(milestone);
        publishStudyEvent({ type: "progress", studyId: SOLA_STUDY_ID, milestone });
      }
    }
    if (next >= 1 && !finishSentRef.current) {
      finishSentRef.current = true;
      publishStudyEvent({ type: "finish", studyId: SOLA_STUDY_ID });
    }
  }, []);

  const updateFromScroll = useCallback(() => {
    const section = sectionRef.current;
    if (!section || staticMode || !activeRef.current || document.hidden) return;
    const rect = section.getBoundingClientRect();
    const raw = Math.max(0, Math.min(1, -rect.top / Math.max(1, rect.height - window.innerHeight)));
    // Fractional CSS pixels can leave the final scroll position just below 1.
    const next = raw >= 0.999 ? 1 : raw;
    commitProgress(next);
  }, [commitProgress, staticMode]);

  const updateActive = useCallback((visible: boolean) => {
    const section = sectionRef.current;
    const active = visible && !document.hidden;
    activeRef.current = active;
    controllerRef.current?.setActive(active);
    if (active && !enteredRef.current) {
      enteredRef.current = true;
      publishStudyEvent({ type: "entry", studyId: SOLA_STUDY_ID });
    }
    if (active) updateFromScroll();
    if (!section) activeRef.current = false;
  }, [updateFromScroll]);

  useEffect(() => {
    const query = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (query) {
      const update = () => setReducedMotion(query.matches);
      update();
      query.addEventListener("change", update);
      setMotionPreferenceReady(true);
      return () => query.removeEventListener("change", update);
    }
    setMotionPreferenceReady(true);
  }, []);

  useEffect(() => {
    setConstrained(isConstrainedDevice());
  }, []);

  useEffect(() => {
    if (!motionPreferenceReady) return;
    if (!canLoadScene) {
      setRenderState("fallback");
      return;
    }
    const section = sectionRef.current;
    const host = hostRef.current;
    if (!section || !host) return;
    const Observer = (window as unknown as { IntersectionObserver?: typeof IntersectionObserver }).IntersectionObserver;
    if (!Observer) {
      setRenderState("fallback");
      return;
    }

    let cancelled = false;
    let started = false;
    const observer = new Observer(async (entries) => {
      if (!entries.some((entry) => entry.isIntersecting) || started) return;
      started = true;
      setRenderState("loading");
      observer.disconnect();
      try {
        const { createSolaScene } = await import("./sola-scene");
        if (cancelled) return;
        const controller = createSolaScene(host, () => setRenderState("fallback"));
        controllerRef.current = controller;
        controller.setProgress(progressRef.current);
        controller.setFinish(finishRef.current);
        controller.setActive(activeRef.current && !document.hidden);
        setRenderState("ready");
      } catch {
        if (!cancelled) setRenderState("fallback");
      }
    }, { rootMargin: "200px 0px" });
    observer.observe(section);
    return () => {
      cancelled = true;
      observer.disconnect();
      controllerRef.current?.dispose();
      controllerRef.current = null;
    };
  }, [canLoadScene, motionPreferenceReady]);

  useEffect(() => {
    const section = sectionRef.current;
    if (!section) return;

    let frame = 0;
    const measureVisibility = () => {
      frame = 0;
      updateActive(sectionIsVisible(section));
    };
    const scheduleVisibility = () => {
      if (!frame) frame = requestAnimationFrame(measureVisibility);
    };
    let observer: IntersectionObserver | null = null;
    const Observer = (window as unknown as { IntersectionObserver?: typeof IntersectionObserver }).IntersectionObserver;
    if (Observer) {
      observer = new Observer((entries) => {
        const entry = entries[0];
        updateActive(Boolean(entry?.isIntersecting && entry.intersectionRatio >= 0.1));
      }, { threshold: [0, 0.1] });
      observer.observe(section);
    } else {
      window.addEventListener("scroll", scheduleVisibility, { passive: true });
      window.addEventListener("resize", scheduleVisibility);
      scheduleVisibility();
    }
    const onVisibilityChange = () => {
      if (document.hidden) updateActive(false);
      else measureVisibility();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      observer?.disconnect();
      window.removeEventListener("scroll", scheduleVisibility);
      window.removeEventListener("resize", scheduleVisibility);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      cancelAnimationFrame(frame);
    };
  }, [updateActive]);

  useEffect(() => {
    if (staticMode) return;
    let frame = 0;
    const update = () => {
      frame = 0;
      updateFromScroll();
    };
    const schedule = () => {
      if (activeRef.current && !frame) frame = requestAnimationFrame(update);
    };
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    schedule();
    return () => {
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      cancelAnimationFrame(frame);
    };
  }, [staticMode, updateFromScroll]);

  useEffect(() => {
    if (renderState !== "fallback") return;
    controllerRef.current?.dispose();
    controllerRef.current = null;
  }, [renderState]);

  const chooseProgress = (next: number) => {
    if (!staticMode && sectionRef.current) {
      const section = sectionRef.current;
      const top = window.scrollY + section.getBoundingClientRect().top +
        next * Math.max(0, section.offsetHeight - window.innerHeight);
      window.scrollTo({ top, behavior: "instant" });
    }
    commitProgress(next);
  };

  const chooseFinish = (index: number) => {
    finishRef.current = index;
    setFinish(index);
    controllerRef.current?.setFinish(index);
  };

  const toggleMotion = () => {
    if (reducedMotion) return;
    const nextPaused = !motionPaused;
    const section = sectionRef.current;
    const sectionTop = section ? window.scrollY + section.getBoundingClientRect().top : window.scrollY;
    setMotionPaused(nextPaused);
    requestAnimationFrame(() => {
      const currentSection = sectionRef.current;
      if (!currentSection) return;
      const top = nextPaused
        ? sectionTop
        : window.scrollY + currentSection.getBoundingClientRect().top +
          progressRef.current * Math.max(0, currentSection.offsetHeight - window.innerHeight);
      window.scrollTo({ top, behavior: "instant" });
    });
  };

  const fallbackStyle = {
    "--study-rotation": String(progress * 360) + "deg",
    "--study-chair-wood": currentFinish.wood,
    "--study-chair-fabric": currentFinish.fabric,
  } as CSSProperties;
  const status = !canLoadScene && motionPreferenceReady ? "fallback" : renderState;
  const fallbackMessage = reducedMotion
    ? "Reduced motion is on. Use the chapters, materials and view slider to explore the still illustration."
    : constrained
      ? "3D is paused on this constrained device. The illustrated study and manual controls remain available."
      : "3D could not start in this browser. The illustrated study and manual controls remain available.";

  return (
    <section
      ref={sectionRef}
      id="sola-study"
      className={"sola-study" + (staticMode ? " is-static" : "")}
      aria-labelledby="sola-study-title"
    >
      <div className="sola-study-stage">
        <div className="sola-study-topline">
          <span>OBJECT STUDY 004 / PROCEDURAL MODEL</span>
          <div className="sola-study-top-actions">
            <button
              className="sola-study-motion"
              type="button"
              aria-pressed={staticMode}
              disabled={reducedMotion}
              onClick={toggleMotion}
            >
              {staticMode ? "Motion off" : "Pause motion"}
            </button>
            <a href="#collection">Skip study <span aria-hidden="true">↓</span></a>
          </div>
        </div>

        <div className="sola-study-intro">
          <p className="eyebrow">MEET SOLA</p>
          <h2 id="sola-study-title">Good from<br /><em>every angle.</em></h2>
          <p className="sola-study-cue">
            <span aria-hidden="true">↓</span>
            {staticMode ? "Choose a view below" : "Scroll slowly. Look closer."}
          </p>
        </div>

        <span className="sola-study-big-type" aria-hidden="true">SOLA</span>
        <div
          ref={hostRef}
          className="sola-study-model"
          role="img"
          aria-label={
            "Procedural Sola chair study in " + currentFinish.name + ". " +
            currentChapter.name + "."
          }
        >
          {status !== "ready" && (
            <svg
              className="sola-study-illustration"
              style={fallbackStyle}
              viewBox="0 0 600 600"
              aria-hidden="true"
            >
              <g fill="none" stroke="var(--study-chair-wood)" strokeWidth="6" strokeLinejoin="round">
                <path d="m180 390-35 125m265-135 35 130M190 185l-40 300m263-276 29 277M185 303l-53 60 278 20 50-48z" />
                <path d="m181 177 201 26 13 122-231-28z" fill="var(--study-chair-fabric)" />
                <path d="m150 330 234 20 38 43-273-19z" fill="var(--study-chair-fabric)" />
                <path d="m142 299 235 25m-229-23 34-124m208 148 18-113" />
              </g>
            </svg>
          )}
        </div>

        <div className="sola-study-caption">
          <p className="eyebrow">0{chapter + 1} / {currentChapter.name}</p>
          <h3>{currentChapter.title}</h3>
          <p>{currentChapter.copy}</p>
        </div>

        <div className="sola-study-finishes">
          <p className="eyebrow">ILLUSTRATIVE MATERIAL PALETTES</p>
          <div className="sola-study-swatches" role="group" aria-label="Study material palettes">
            {finishes.map((item, index) => (
              <button
                key={item.name}
                className={"sola-study-swatch" + (finish === index ? " selected" : "")}
                type="button"
                aria-label={item.name}
                aria-pressed={finish === index}
                onClick={() => chooseFinish(index)}
                style={{ background: "linear-gradient(135deg, " + item.wood + " 50%, " + item.fabric + " 50%)" }}
              >
                {finish === index && <span aria-hidden="true">✓</span>}
              </button>
            ))}
          </div>
          <span className="sola-study-finish-name">{currentFinish.name}</span>
          <p className="sola-study-not-product">Study palettes only. This procedural model is not a stocked product.</p>
          <Link className="sola-study-link" href="/shop">Browse the collection <span aria-hidden="true">↗</span></Link>
        </div>

        <div className="sola-study-controls">
          <div className="sola-study-chapters" role="group" aria-label="Chair study chapters">
            {chapters.map((item, index) => (
              <button
                key={item.name}
                className={chapter === index ? "selected" : ""}
                type="button"
                aria-pressed={chapter === index}
                onClick={() => chooseProgress(chapterPositions[index])}
              >
                <span aria-hidden="true">0{index + 1}</span>
                {item.name}
              </button>
            ))}
          </div>
          <label className="sola-study-scrubber">
            <span className="sr-only">Rotate and explore the Sola chair study</span>
            <input
              type="range"
              min="0"
              max="100"
              value={Math.round(progress * 100)}
              aria-valuetext={currentChapter.name + ", " + Math.round(progress * 360) + " degrees"}
              onChange={(event) => chooseProgress(Number(event.target.value) / 100)}
            />
            <span aria-hidden="true">{Math.round(progress * 360)}°</span>
          </label>
        </div>

        {status === "fallback" && (
          <p className="sola-study-fallback" role="status">{fallbackMessage}</p>
        )}
      </div>
    </section>
  );
}
