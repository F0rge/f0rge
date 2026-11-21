export interface PublicFieldError {
  field: string;
  code: string;
  message: string;
}
export class ApiFailure extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly errorId?: string,
    readonly fields: readonly PublicFieldError[] = [],
  ) {
    super(message);
    this.name = "ApiFailure";
  }
  get denied() {
    return this.status === 401 || this.status === 403;
  }
  get conflict() {
    return this.status === 409;
  }
}
function object(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Only documented public fields are surfaced; raw response/debug data is never shown. */
export function apiFailure(status: number, body: unknown): ApiFailure {
  const error = object(body) && object(body.error) ? body.error : undefined;
  const code = typeof error?.code === "string" ? error.code : "request_failed";
  const message =
    typeof error?.message === "string"
      ? error.message
      : status === 409
        ? "Your saved data changed. Reload before trying again."
        : status === 401
          ? "Sign in to continue."
          : status === 403
            ? "This account does not have access."
            : "The request could not be completed. Try again.";
  const fields = Array.isArray(error?.field_errors)
    ? error.field_errors.filter(
        (entry): entry is PublicFieldError =>
          object(entry) &&
          typeof entry.field === "string" &&
          typeof entry.code === "string" &&
          typeof entry.message === "string",
      )
    : [];
  return new ApiFailure(
    status,
    code,
    message,
    typeof error?.error_id === "string" ? error.error_id : undefined,
    fields,
  );
}
