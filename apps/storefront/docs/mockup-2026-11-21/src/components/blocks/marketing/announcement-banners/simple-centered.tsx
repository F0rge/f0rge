import { Link, type Route } from '@/lib/router';

export interface SimpleCenteredProps {
  text: string;
  detail: string;
  to: Route;
}

export default function SimpleCentered({ text, detail, to }: SimpleCenteredProps) {
  return (
    <div className="bg-muted">
      <div className="container mx-auto px-4 md:px-6 2xl:max-w-[1400px]">
        <div className="flex items-center justify-between gap-x-6 p-4">
          <div className="flex w-full items-center gap-x-4 text-sm">
            <p className="flex-1 text-center">
              <Link
                to={to}
                className="font-semibold underline-offset-4 hover:underline"
              >
                {text}
              </Link>
              <span className="hidden sm:inline">
                {' '}
                {detail}
              </span>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
