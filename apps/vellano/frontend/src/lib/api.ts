export type UserRole = "owner" | "buyer" | "warehouse" | "till" | "books";

export type Team = {
  id: string;
  name: string;
};

export type AuthUser = {
  id: string;
  email: string;
  role: UserRole;
  team: Team;
  display_name: string | null;
};

export type User = {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
  is_disabled: boolean;
  team_id: string;
  team: Team;
};

export type LoginResponse = {
  email: string;
};

export type CreateUserPayload = {
  email: string;
  password: string;
  role: UserRole;
  display_name?: string;
};

export type UpdateUserPayload = {
  email?: string;
  password?: string;
  role?: UserRole;
  display_name?: string;
  is_disabled?: boolean;
};

export type UpdateProfilePayload = {
  email?: string;
  display_name?: string;
  password?: string;
};

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function parseErrorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string | { msg?: string }[] };
    if (typeof body.detail === "string") {
      return body.detail;
    }
    if (Array.isArray(body.detail) && body.detail[0]?.msg) {
      return body.detail[0].msg;
    }
  } catch {
    // ignore parse errors
  }
  return response.statusText || "Request failed";
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`/api/v1${path}`, {
    ...options,
    credentials: "include",
    headers,
  });

  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export function login(email: string, password: string): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function logout(): Promise<void> {
  return apiFetch<void>("/auth/logout", { method: "POST" });
}

export function getMe(): Promise<AuthUser> {
  return apiFetch<AuthUser>("/auth/me");
}

export function listUsers(): Promise<User[]> {
  return apiFetch<User[]>("/users");
}

export function createUser(payload: CreateUserPayload): Promise<User> {
  return apiFetch<User>("/users", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateUser(id: string, payload: UpdateUserPayload): Promise<User> {
  return apiFetch<User>(`/users/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function updateProfile(payload: UpdateProfilePayload): Promise<AuthUser> {
  return apiFetch<AuthUser>("/profile", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export const USER_ROLES: { value: UserRole; label: string }[] = [
  { value: "owner", label: "Owner" },
  { value: "buyer", label: "Buyer" },
  { value: "warehouse", label: "Warehouse" },
  { value: "till", label: "Till" },
  { value: "books", label: "Books" },
];

export type LocationType = "warehouse" | "showroom";

export type Location = {
  id: string;
  name: string;
  type: LocationType;
  is_archived: boolean;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
};

export type CreateLocationPayload = {
  name: string;
  type: LocationType;
};

export type UpdateLocationPayload = {
  name?: string;
  is_archived?: boolean;
};

export function listLocations(): Promise<Location[]> {
  return apiFetch<Location[]>("/locations");
}

export function createLocation(payload: CreateLocationPayload): Promise<Location> {
  return apiFetch<Location>("/locations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateLocation(id: string, payload: UpdateLocationPayload): Promise<Location> {
  return apiFetch<Location>(`/locations/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export const LOCATION_TYPES: { value: LocationType; label: string }[] = [
  { value: "warehouse", label: "Warehouse" },
  { value: "showroom", label: "Showroom" },
];

export function isActiveLocation(loc: Location): boolean {
  return !loc.is_archived;
}
