"use client";

import { HeaderGlobalAction } from "@carbon/react";
import { Compass, Help } from "@carbon/icons-react";
import { usePathname, useRouter } from "next/navigation";
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
import { OVERVIEW_STEPS, pageTourForPath } from "@/lib/tour-steps";
import {
  writeOverviewCompletion,
  writePageTourCompletion,
  type TourCompletion,
} from "@/lib/tour-storage";

type TourMode = "page" | "overview";

type TourContextValue = {
  startPageTour: () => void;
  startOverviewTour: () => void;
  pageTourAvailable: boolean;
  running: TourMode | null;
};

const TourContext = createContext<TourContextValue | null>(null);

type TourProviderProps = {
  userId: string;
  children: ReactNode;
};

export function TourProvider({ userId, children }: TourProviderProps) {
  const router = useRouter();
  const pathname = usePathname();
  const navigate = useCallback(
    (route: string) => {
      router.push(route);
    },
    [router],
  );

  const pageTour = pageTourForPath(pathname);
  const [mode, setMode] = useState<TourMode>("page");
  const [run, setRun] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);

  const definitions = useMemo(
    () => (mode === "overview" ? OVERVIEW_STEPS : (pageTour?.steps ?? [])),
    [mode, pageTour],
  );
  const steps = useMemo(
    () => buildJoyrideSteps(definitions, navigate),
    [definitions, navigate],
  );

  const finish = useCallback(
    (completion: TourCompletion) => {
      if (mode === "overview") {
        writeOverviewCompletion(userId, completion);
      } else if (pageTour) {
        writePageTourCompletion(userId, pageTour.id, completion);
      }
      setRun(false);
      setStepIndex(0);
    },
    [mode, pageTour, userId],
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
      width: 360,
    },
  });

  const begin = useCallback((next: TourMode) => {
    setMode(next);
    setStepIndex(0);
    setRun(false);
    window.setTimeout(() => {
      setRun(true);
    }, 0);
  }, []);

  const startPageTour = useCallback(() => {
    if (!pageTour) {
      return;
    }
    begin("page");
  }, [begin, pageTour]);

  const startOverviewTour = useCallback(() => {
    begin("overview");
  }, [begin]);

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

  const value = useMemo(
    () => ({
      startPageTour,
      startOverviewTour,
      pageTourAvailable: pageTour !== null,
      running: run ? mode : null,
    }),
    [mode, pageTour, run, startOverviewTour, startPageTour],
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

export function PageTourButton() {
  const { running, startPageTour, pageTourAvailable } = useTour();
  if (!pageTourAvailable) {
    return null;
  }
  return (
    <HeaderGlobalAction
      aria-label={running === "page" ? "Restart page tour" : "Page tour"}
      tooltipAlignment="end"
      onClick={() => startPageTour()}
    >
      <Help size={20} />
    </HeaderGlobalAction>
  );
}

export function OverviewTourButton() {
  const { running, startOverviewTour } = useTour();
  return (
    <HeaderGlobalAction
      aria-label={running === "overview" ? "Restart overview tour" : "Overview tour"}
      tooltipAlignment="end"
      onClick={() => startOverviewTour()}
    >
      <Compass size={20} />
    </HeaderGlobalAction>
  );
}
