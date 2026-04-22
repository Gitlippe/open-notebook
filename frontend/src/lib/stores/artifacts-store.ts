import { create } from 'zustand'

import { ArtifactType } from '@/lib/types/artifacts'

// ---------------------------------------------------------------------------
// State shape
// ---------------------------------------------------------------------------

interface ArtifactsState {
  /** Job ID of the most recently submitted / currently monitored generation job. */
  activeJobId: string | null

  /** Artifact type currently selected in the generate dialog. */
  selectedArtifactType: ArtifactType | null

  /** Source record IDs selected by the user as inputs for generation. */
  sourcesSelection: string[]

  /** Free-form config key/values accumulated through the generate dialog. */
  configDraft: Record<string, unknown>

  // Setters ----------------------------------------------------------------

  setActiveJobId: (jobId: string | null) => void
  setSelectedArtifactType: (artifactType: ArtifactType | null) => void
  setSourcesSelection: (sources: string[]) => void
  addSource: (sourceId: string) => void
  removeSource: (sourceId: string) => void
  setConfigDraft: (config: Record<string, unknown>) => void
  patchConfigDraft: (patch: Record<string, unknown>) => void

  /** Reset UI state (e.g. when the dialog closes). */
  reset: () => void
}

// ---------------------------------------------------------------------------
// Default values
// ---------------------------------------------------------------------------

const DEFAULT_STATE = {
  activeJobId: null,
  selectedArtifactType: null,
  sourcesSelection: [] as string[],
  configDraft: {} as Record<string, unknown>,
} satisfies Pick<
  ArtifactsState,
  'activeJobId' | 'selectedArtifactType' | 'sourcesSelection' | 'configDraft'
>

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useArtifactsStore = create<ArtifactsState>()((set) => ({
  ...DEFAULT_STATE,

  setActiveJobId: (jobId) => set({ activeJobId: jobId }),

  setSelectedArtifactType: (artifactType) =>
    set({ selectedArtifactType: artifactType }),

  setSourcesSelection: (sources) => set({ sourcesSelection: sources }),

  addSource: (sourceId) =>
    set((state) => ({
      sourcesSelection: state.sourcesSelection.includes(sourceId)
        ? state.sourcesSelection
        : [...state.sourcesSelection, sourceId],
    })),

  removeSource: (sourceId) =>
    set((state) => ({
      sourcesSelection: state.sourcesSelection.filter((id) => id !== sourceId),
    })),

  setConfigDraft: (config) => set({ configDraft: config }),

  patchConfigDraft: (patch) =>
    set((state) => ({
      configDraft: { ...state.configDraft, ...patch },
    })),

  reset: () => set(DEFAULT_STATE),
}))
