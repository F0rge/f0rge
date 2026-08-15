'use client';

import { useEffect } from 'react';
import { driver } from 'driver.js';
import 'driver.js/dist/driver.css';
import { GraduationCap } from 'lucide-react';
import { Button } from '@f0rge/ui';

function startTour() {
  const tour = driver({
    showProgress: true,
    allowClose: true,
    nextBtnText: 'Next',
    prevBtnText: 'Back',
    doneBtnText: 'Done',
    onDestroyStarted: () => {
      localStorage.setItem('dk-tour-v1', '1');
      tour.destroy();
    },
    steps: [
      {
        popover: {
          title: 'Welcome 👋',
          description:
            'This tool turns a DEAR Inventory CSV export into printable price tags. Take a quick 30-second tour?',
        },
      },
      {
        element: '[data-tour="config"]',
        popover: {
          title: 'Tag settings',
          description:
            'Set orientation, tag size and font here — all editable before you upload anything.',
          side: 'right',
          align: 'start',
        },
      },
      {
        element: '[data-tour="alignment"]',
        popover: {
          title: 'Sticker-sheet alignment',
          description:
            'The key part: nudge these margins so tags line up with your physical sticker sheet and the P-reference is not cropped when you peel them off.',
          side: 'right',
          align: 'start',
        },
      },
      {
        element: '[data-tour="preview"]',
        popover: {
          title: 'Live preview',
          description:
            'This A4 preview updates as you type. Match it to your sheet before printing.',
          side: 'right',
          align: 'start',
        },
      },
      {
        element: '[data-tour="upload"]',
        popover: {
          title: 'Upload your CSV',
          description:
            'Start here — drag in or click to browse your DEAR Inventory export.',
          side: 'left',
          align: 'start',
        },
      },
      {
        popover: {
          title: "That's it!",
          description:
            'After uploading you will search & pick products, then hit Generate to download your PDF. Replay this tour any time from the top-right.',
        },
      },
    ],
  });

  tour.drive();
}

export default function Tour() {
  useEffect(() => {
    if (localStorage.getItem('dk-tour-v1') !== null) return;
    const t = setTimeout(startTour, 600);
    return () => clearTimeout(t);
  }, []);

  return (
    <Button
      type="button"
      variant="outline"
      size="icon-sm"
      onClick={startTour}
      aria-label="Take a tour"
      title="Take a tour"
    >
      <GraduationCap />
    </Button>
  );
}
