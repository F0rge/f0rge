import type { UpdateUserPayload, User } from "./api";

export type UserEditForm = {
  display_name: string;
  role: string;
  default_location_id: string;
};

/** Sign-in credentials belong to Clerk; this payload contains local access/preferences only. */
export function userEditPayload(user: User, form: UserEditForm): UpdateUserPayload {
  const payload: UpdateUserPayload = { role: form.role };
  if (form.display_name !== user.display_name) payload.display_name = form.display_name;
  const location = form.default_location_id || null;
  if (location !== (user.default_location_id ?? null)) payload.default_location_id = location;
  return payload;
}
