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
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { EVENTS, STATUS, useJoyride, type EventData } from "react-joyride";

import { TourTooltip } from "@/components/tour/tour-tooltip";
import {
  getSideNavExpandedSnapshot,
  setSideNavExpanded,
} from "@/lib/side-nav-preference";
import {
  buildJoyrideSteps,
  cancelTourNavigation,
  releaseTourBlockers,
} from "@/lib/tour-navigation";
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
  nia: boolean;
  children: ReactNode;
};

export function TourProvider({ userId, nia, children }: TourProviderProps) {
  const router = useRouter();
  const navigate = useCallback(
    (route: string) => {
      router.push(route);
    },
    [router],
  );

  const [run, setRun] = useState(false);
  const steps = useMemo(
    () => buildJoyrideSteps(stepsForUser({ nia }), navigate),
    [navigate, nia],
  );
  const navBeforeTour = useRef<boolean | null>(null);
  const hasStarted = useRef(false);
  const ended = useRef(false);

  const endTour = useCallback(
    (completion: TourCompletion) => {
      if (ended.current) {
        return;
      }
      ended.current = true;
      cancelTourNavigation();
      writeTourCompletion(userId, completion);
      if (navBeforeTour.current !== null) {
        setSideNavExpanded(navBeforeTour.current);
        navBeforeTour.current = null;
      }
      setRun(false);
    },
    [userId],
  );

  const onEvent = useCallback(
    (data: EventData) => {
      const { type, status } = data;
      if (type === EVENTS.TOUR_END || status === STATUS.FINISHED || status === STATUS.SKIPPED) {
        endTour(status === STATUS.SKIPPED ? "skipped" : "completed");
      }
    },
    [endTour],
  );

  const { Tour, controls } = useJoyride({
    run,
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
      // Joyride only handles Escape while the tooltip is open. The listener
      // below skips during the wait, when the mask is up and the tooltip is not.
      dismissKeyAction: false,
      blockTargetInteraction: true,
      spotlightPadding: 8,
      spotlightRadius: 0,
      // before() already waited. A missing node should skip quickly, not pin the mask.
      targetWaitTimeout: 400,
      beforeTimeout: 8000,
      zIndex: 12000,
      primaryColor: "#0f62fe",
      backgroundColor: "#ffffff",
      textColor: "#161616",
      overlayColor: "rgba(22, 22, 22, 0.6)",
      arrowColor: "#ffffff",
      width: 416,
    },
  });

  const dismiss = useCallback(() => {
    endTour("skipped");
    controls.skip();
  }, [controls, endTour]);

  const startTour = useCallback(() => {
    ended.current = false;
    navBeforeTour.current = getSideNavExpandedSnapshot();
    hasStarted.current = true;
    setRun(false);
    window.setTimeout(() => {
      controls.reset(false);
      setRun(true);
    }, 0);
  }, [controls]);

  useEffect(() => {
    if (!run) {
      return;
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      dismiss();
    };
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, [dismiss, run]);

  useEffect(() => {
    if (run) {
      hasStarted.current = true;
      if (navBeforeTour.current === null) {
        navBeforeTour.current = getSideNavExpandedSnapshot();
      }
      return;
    }
    if (!hasStarted.current) {
      return;
    }
    releaseTourBlockers();
  }, [run]);

  useEffect(() => {
    if (readTourCompletion(userId)) {
      return;
    }
    const timer = window.setTimeout(() => {
      ended.current = false;
      hasStarted.current = true;
      navBeforeTour.current = getSideNavExpandedSnapshot();
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

  const dismissButton =
    run && typeof document !== "undefined"
      ? createPortal(
          <button
            type="button"
            className="firstout-tour-dismiss"
            autoFocus
            onClick={() => dismiss()}
          >
            Skip tour
          </button>,
          document.body,
        )
      : null;

  return (
    <TourContext.Provider value={value}>
      {children}
      {Tour}
      {dismissButton}
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
