/**
 * Remembers the last resolved company code, so a returning caller can skip
 * straight to the Email + Password screen instead of retyping it.
 *
 * Storage lifetime differs by client, per the desktop/web distinction:
 *   - web (VITE_APP_MODE unset/"web"): sessionStorage - remembered only for
 *     the current browser tab/session, forgotten once it's closed. A shared
 *     browser shouldn't silently remember which company someone last used
 *     across sessions.
 *   - desktop (VITE_APP_MODE="desktop", set by the Electron build):
 *     localStorage - remembered across app launches, exactly like a native
 *     app would. There is no Electron shell yet (it arrives in a later
 *     milestone), but this env-var gate needs no changes when it does -
 *     the Electron build simply sets VITE_APP_MODE=desktop.
 * Both clients get the same "Change Company" affordance (clears the stored
 * value and returns to the company-code screen); only how long the value
 * survives differs.
 */

export interface RememberedCompany {
  companyCode: string;
  companyName: string;
  companyLogo: string | null;
}

const STORAGE_KEY = "itonit.companyCode";

function storage(): Storage {
  return import.meta.env.VITE_APP_MODE === "desktop" ? localStorage : sessionStorage;
}

export const companyStore = {
  get(): RememberedCompany | null {
    const raw = storage().getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    try {
      return JSON.parse(raw) as RememberedCompany;
    } catch {
      return null;
    }
  },

  set(company: RememberedCompany): void {
    storage().setItem(STORAGE_KEY, JSON.stringify(company));
  },

  clear(): void {
    storage().removeItem(STORAGE_KEY);
  },
};
