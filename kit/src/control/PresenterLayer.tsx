// Presenter mode overlay: tiny ⌨ mark (key map on hover), key handling, 1-second toast. Keys call the real Core.
import { useEffect, useRef, useState } from "react";
import { apiRequest, type ApiConfig } from "./api";
import { KEY_MAP, presenterRequest, type CallerRole, type PresenterCtx } from "./presenter";

export interface PresenterLayerProps {
  api: ApiConfig;
  ctx: Omit<PresenterCtx, "caller">;
  onNextVillage: () => void;
  onDetails: () => void;
  onReselect: () => void;
  /** extra keys handled by the room (ROOM-7) */
  extraKeys?: Record<string, () => string | void>;
  extraMap?: [string, string][];
}

export function PresenterLayer({ api, ctx, onNextVillage, onDetails, onReselect, extraKeys = {}, extraMap = [] }: PresenterLayerProps) {
  const [caller, setCaller] = useState<CallerRole>("elder");
  const [toast, setToast] = useState<string | null>(null);
  const [mapOpen, setMapOpen] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const say = (t: string) => {
    setToast(t);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setToast(null), 1000);
  };
  const real: ApiConfig = { ...api, fake: false };
  const latest = useRef({ ctx, caller });
  latest.current = { ctx, caller };

  useEffect(() => {
    const on = async (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const k = e.key;
      if (k === "Escape") return setMapOpen(false);
      if (k === "v" || k === "V") return onNextVillage();
      if (k === "d" || k === "D") return onDetails();
      const extra = extraKeys[k.toLowerCase()];
      if (extra) {
        const t = extra();
        if (t) say(t);
        return;
      }
      const req = presenterRequest(k, { ...latest.current.ctx, caller: latest.current.caller });
      if (!req) {
        if (k.toLowerCase() === "a") say("Nothing waiting for a yes");
        return;
      }
      e.preventDefault();
      try {
        await apiRequest(real, req.method, req.path, req.body, req.headers);
        say(req.toast);
        if (req.after === "caller") setCaller((c) => (c === "elder" ? "unknown" : "elder"));
        if (req.after === "reselect") onReselect();
      } catch (err) {
        say(`Core didn't take that (${err instanceof Error ? err.message : "error"})`);
      }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [api, onNextVillage, onDetails, onReselect, extraKeys]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <div className={`presenter-mark${mapOpen ? " open" : ""}`} data-test="presenter-mark" onMouseEnter={() => setMapOpen(true)} onMouseLeave={() => setMapOpen(false)}>
        <span aria-hidden="true">⌨</span>
        {mapOpen ? (
          <table className="key-map" data-test="key-map">
            <tbody>
              {[...KEY_MAP.slice(0, -1), ...extraMap, KEY_MAP[KEY_MAP.length - 1]].map(([key, what]) => (
                <tr key={key}><th>{key}</th><td>{key === "U" ? `${what} · now: ${caller === "elder" ? "elder" : "unknown caller"}` : what}</td></tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </div>
      {toast ? <div className="presenter-toast" data-test="presenter-toast" role="status">{toast}</div> : null}
    </>
  );
}
