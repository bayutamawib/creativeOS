"use client";
import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { mutate } from "@/lib/browser-api";
export type Member = {
  id: string;
  full_name: string;
  email: string;
  roles: { role: string; is_active: boolean }[];
  manageable_roles: string[];
};
const names: Record<string, string> = {
  admin: "Admin",
  agency_manager: "Agency Manager",
  team_member: "Team Member",
};
export function AgencyMembers({
  members,
  timezone,
  admin,
}: {
  members: Member[];
  timezone: string;
  admin: boolean;
}) {
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [link, setLink] = useState("");
  async function saveTimezone(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      await mutate("/agency/settings/operations", "PATCH", {
        timezone: data.get("timezone"),
      });
      setMessage("Agency timezone saved");
      router.refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Update failed");
    }
  }
  async function invite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setLink("");
    setMessage("");
    try {
      const invitation = await mutate("/agency/invitations", "POST", {
        email: form.get("email"),
        role: form.get("role"),
      });
      setLink(
        window.location.origin + "/accept-invitation#" + invitation.token,
      );
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Invitation failed");
    }
  }
  async function change(
    member: Member,
    role: string,
    method: string,
    active?: boolean,
  ) {
    try {
      await mutate(
        "/agency/members/" + member.id + "/roles/" + role,
        method,
        active === undefined ? undefined : { is_active: active },
      );
      setMessage("Membership updated");
      router.refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Update failed");
    }
  }
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Agency members</h2>
      <ul className="divide-y divide-border">
        {members.map((member) => (
          <li className="py-4" key={member.id}>
            <p className="font-medium">{member.full_name}</p>
            <p className="text-sm text-slate-600">{member.email}</p>
            {member.roles.map(({ role, is_active }) => (
              <div
                className="mt-2 flex flex-wrap items-center gap-2 text-sm"
                key={role}
              >
                <span>
                  {names[role]} · {is_active ? "Active" : "Inactive"}
                </span>
                {member.manageable_roles.includes(role) && (
                  <>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => change(member, role, "PATCH", !is_active)}
                    >
                      {is_active ? "Deactivate" : "Activate"}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => change(member, role, "DELETE")}
                    >
                      Revoke role
                    </Button>
                  </>
                )}
              </div>
            ))}
            {member.manageable_roles
              .filter((r) => !member.roles.some((m) => m.role === r))
              .map((r) => (
                <Button
                  key={r}
                  variant="ghost"
                  size="sm"
                  onClick={() => change(member, r, "PUT")}
                >
                  Grant {names[r]}
                </Button>
              ))}
          </li>
        ))}
      </ul>
      <form
        method="post"
        onSubmit={invite}
        className="flex flex-wrap items-end gap-3 border-t border-border pt-6"
      >
        <label className="text-sm">
          Invite by email
          <input type="email" name="email" required />
        </label>
        <label className="text-sm">
          Agency role
          <select
            className="block rounded border border-border p-2"
            name="role"
            defaultValue="team_member"
          >
            {(admin ? Object.keys(names) : ["team_member"]).map((role) => (
              <option key={role} value={role}>
                {names[role]}
              </option>
            ))}
          </select>
        </label>
        <Button>Create invitation</Button>
      </form>
      {link && (
        <label className="block text-sm">
          Private invitation link
          <input readOnly value={link} onFocus={(e) => e.target.select()} />
        </label>
      )}
      <form
        method="post"
        onSubmit={saveTimezone}
        className="flex items-end gap-3 border-t border-border pt-6"
      >
        <label className="text-sm">
          Agency timezone
          <input name="timezone" defaultValue={timezone} required />
        </label>
        <Button variant="outline">Save timezone</Button>
      </form>
      <p role="status" className="text-sm">
        {message}
      </p>
    </div>
  );
}
