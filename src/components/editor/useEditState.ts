import { useState, useCallback, useRef } from "react";
import { editState, type EditState } from "@/lib/api";

const JOB_ID_KEY = "auteur_current_job_id";

export interface ChatAttachment {
  id: string;
  type: "youtube" | "image" | "music" | "file" | "link";
  label: string;
  url: string;
  thumbnail?: string;
}

export function useEditState() {
  const [state, setState] = useState<EditState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dirtyRanges, setDirtyRanges] = useState<{ start: number; end: number }[]>([]);
  const [jobId, setJobIdState] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    return sessionStorage.getItem(JOB_ID_KEY);
  });
  const jobIdRef = useRef<string | null>(null);

  if (jobIdRef.current !== jobId) jobIdRef.current = jobId;

  const getJobId = useCallback(() => {
    if (jobIdRef.current) return jobIdRef.current;
    if (typeof window === "undefined") return null;
    const stored = sessionStorage.getItem(JOB_ID_KEY);
    if (stored) { jobIdRef.current = stored; setJobIdState(stored); return stored; }
    return null;
  }, []);

  const setJobId = useCallback((id: string) => {
    jobIdRef.current = id;
    sessionStorage.setItem(JOB_ID_KEY, id);
    setJobIdState(id);
  }, []);

  const loadState = useCallback(async (id: string) => {
    setLoading(true); setError(null);
    try {
      setJobId(id);
      const res = await editState.get(id);
      setState(res.state);
      setDirtyRanges(res.dirty_ranges);
    } catch (e: any) {
      setError(e.message);
    } finally { setLoading(false); }
  }, [setJobId]);

  const createJob = useCallback(async (videoId: string) => {
    setLoading(true); setError(null);
    try {
      const res = await editState.create(videoId);
      setJobId(res.job_id);
      setState(res.state);
      setDirtyRanges(res.dirty_ranges);
      return res.job_id;
    } catch (e: any) {
      setError(e.message);
      return null;
    } finally { setLoading(false); }
  }, [setJobId]);

  const applyActions = useCallback(async (actions: any[]) => {
    const jobId = getJobId();
    if (!jobId || !state) return;
    try {
      const res = await editState.patch(jobId, actions);
      setState(res.state);
      setDirtyRanges(res.dirty_ranges);
    } catch (e: any) {
      setError(e.message);
    }
  }, [state, getJobId]);

  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const applyActionsDebounced = useCallback((actions: any[]) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => applyActions(actions), 100);
  }, [applyActions]);

  const sendPrompt = useCallback(async (prompt: string, attachments?: ChatAttachment[]) => {
    const jobId = getJobId();
    if (!jobId) return null;
    try {
      const res = await editState.prompt(jobId, prompt, attachments);
      const fresh = await editState.get(jobId);
      setState(fresh.state);
      setDirtyRanges(fresh.dirty_ranges);
      if (res.applied_patches.length > 0 && (res.needs_render || res.applied_patches.some((p: any) => p.needs_render))) {
        try { await editState.render(jobId); } catch {}
      }
      return res;
    } catch (e: any) {
      setError(e.message);
      return null;
    }
  }, [getJobId]);

  const undoAction = useCallback(async () => {
    const jobId = getJobId();
    if (!jobId) return;
    const res = await editState.undo(jobId);
    setState(res.state);
  }, [getJobId]);

  const redoAction = useCallback(async () => {
    const jobId = getJobId();
    if (!jobId) return;
    const res = await editState.redo(jobId);
    setState(res.state);
  }, [getJobId]);

  const renderDirty = useCallback(async () => {
    const jobId = getJobId();
    if (!jobId) return null;
    return await editState.render(jobId);
  }, [getJobId]);

  const exportVideo = useCallback(async () => {
    const jobId = getJobId();
    if (!jobId) return null;
    return await editState.export(jobId);
  }, [getJobId]);

  const autoEdit = useCallback(async () => {
    const jobId = getJobId();
    if (!jobId) return null;
    const res = await editState.autoEdit(jobId);
    if (res) {
      const fresh = await editState.get(jobId);
      setState(fresh.state);
      setDirtyRanges(fresh.dirty_ranges);
    }
    return res;
  }, [getJobId]);

  const previewRender = useCallback(async () => {
    const jobId = getJobId();
    if (!jobId) return null;
    return await editState.previewRender(jobId);
  }, [getJobId]);

  const detectHighlights = useCallback(async () => {
    const jobId = getJobId();
    if (!jobId) return null;
    return await editState.detectHighlights(jobId);
  }, [getJobId]);

  return {
    state, setState, loading, error, dirtyRanges,
    loadState, createJob, applyActions, applyActionsDebounced, sendPrompt,
    undoAction, redoAction, renderDirty, exportVideo, autoEdit,
    previewRender, detectHighlights,
    jobId,
  };
}
