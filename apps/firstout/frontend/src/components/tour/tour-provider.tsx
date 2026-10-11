"use client";

import { HeaderGlobalAction } from "@carbon/react";
import { Help } from "@carbon/icons-react";
import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { ACTIONS, EVENTS, STATUS, useJoyride, type EventData } from "react-joyride";

import { TourTooltip } from "@/components/tour/tour-tooltip";
import { buildJoyrideSteps } from "@/lib/tour-navigation";
import { stepsForUser } from "@/lib/tour-steps";
import {
  readTourCompletion,
  writeTourCompletion,
  type TourCompletion,
} from "@/lib/tour-storage";

type TourContextValue = {
  startTour: () => void;
  isRunning: boolean;
};

const TourContext = createContext<TourContextValue | null>(null);

type TourProviderProps = {
  userId: string;
  children: ReactNode;
};

export function TourProvider({ userId, children }: TourProviderProps) {
  const router = useRouter();
  const navigate = useCallback(
    (route: string) => {
      router.push(route);
    },
    [router],
  );

  const [run, setRun] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const steps = useMemo(
    () => buildJoyrideSteps(stepsForUser(), navigate),
    [navigate],
  );

  const finish = useCallback(
    (completion: TourCompletion) => {
      writeTourCompletion(userId, completion);
      setRun(false);
      setStepIndex(0);
    },
    [userId],
  );

  const onEvent = useCallback(
    (data: EventData) => {
      const { type, action, index, status } = data;

      if (type === EVENTS.STEP_AFTER && status === STATUS.RUNNING) {
        if (action === ACTIONS.NEXT) {
          setStepIndex(index + 1);
        } else if (action === ACTIONS.PREV) {
          setStepIndex(Math.max(0, index - 1));
        }
      }

      if (type === EVENTS.TARGET_NOT_FOUND) {
        setStepIndex((current) => (current + 1 >= steps.length ? current : current + 1));
      }

      if (type === EVENTS.TOUR_END || status === STATUS.FINISHED || status === STATUS.SKIPPED) {
        const skipped = status === STATUS.SKIPPED || action === ACTIONS.SKIP;
        finish(skipped ? "skipped" : "completed");
      }
    },
    [finish, steps.length],
  );

  const { Tour, controls } = useJoyride({
    run,
    stepIndex,
    steps,
    continuous: true,
    scrollToFirstStep: true,
    onEvent,
    tooltipComponent: TourTooltip,
    locale: {
      skip: "Skip tour",
      last: "Done",
      next: "Next",
      back: "Back",
      close: "Skip tour",
    },
    options: {
      buttons: ["skip", "back", "close", "primary"],
      closeButtonAction: "skip",
      skipBeacon: true,
      showProgress: false,
      overlayClickAction: false,
      dismissKeyAction: false,
      blockTargetInteraction: true,
      spotlightPadding: 8,
      spotlightRadius: 0,
      targetWaitTimeout: 8000,
      beforeTimeout: 20000,
      zIndex: 12000,
      primaryColor: "#0f62fe",
      backgroundColor: "#ffffff",
      textColor: "#161616",
      overlayColor: "rgba(22, 22, 22, 0.6)",
      arrowColor: "#ffffff",
      width: 416,
    },
  });

  const startTour = useCallback(() => {
    setStepIndex(0);
    setRun(false);
    window.setTimeout(() => {
      setRun(true);
    }, 0);
  }, []);

  useEffect(() => {
    if (!run) {
      return;
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") {
        return;
      }
      event.preventDefault();
      controls.skip();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [controls, run]);

  useEffect(() => {
    if (readTourCompletion(userId)) {
      return;
    }
    const timer = window.setTimeout(() => {
      setStepIndex(0);
      setRun(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [userId]);

  const value = useMemo(
    () => ({
      startTour,
      isRunning: run,
    }),
    [run, startTour],
  );

  return (
    <TourContext.Provider value={value}>
      {children}
      {Tour}
    </TourContext.Provider>
  );
}

export function useTour(): TourContextValue {
  const context = useContext(TourContext);
  if (!context) {
    throw new Error("useTour must be used within TourProvider");
  }
  return context;
}

export function TourReplayButton() {
  const { isRunning, startTour } = useTour();
  return (
    <HeaderGlobalAction
      aria-label={isRunning ? "Restart app tour" : "App tour"}
      tooltipAlignment="end"
      onClick={() => startTour()}
    >
      <Help size={20} />
    </HeaderGlobalAction>
  );
}
