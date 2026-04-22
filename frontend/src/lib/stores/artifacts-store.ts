import { create } from 'zustand'

import { ArtifactJobResult, ArtifactType } from '@/lib/types/artifacts'

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

  /** Per-session history of successfully completed artifact jobs (UI only). */
  completedArtifacts: ArtifactJobResult[]

  /** Whether the GenerateArtifactDialog is open. */
  isGenerateDialogOpen: boolean

  /** Job ID of the artifact currently being previewed in the modal. */
  previewJobId: string | null

  // Setters ----------------------------------------------------------------

  setActiveJobId: (jobId: string | null) => void
  setSelectedArtifactType: (artifactType: ArtifactType | null) => void
  setSourcesSelection: (sources: string[]) => void
  addSource: (sourceId: string) => void
  removeSource: (sourceId: string) => void
  setConfigDraft: (config: Record<string, unknown>) => void
  patchConfigDraft: (patch: Record<string, unknown>) => void

  /** Append an artifact to the session history (idempotent on job_id). */
  addCompletedArtifact: (artifact: ArtifactJobResult) => void

  /** Show the generate dialog. */
  openGenerateDialog: () => void

  /** Hide the generate dialog (also resets draft state). */
  closeGenerateDialog: () => void

  /** Switch which artifact is shown in the preview modal. */
  setPreviewJobId: (jobId: string | null) => void

  /** Reset draft UI state (dialog inputs). Leaves session history intact. */
  reset: () => void
}

// ---------------------------------------------------------------------------
// Default values
// ---------------------------------------------------------------------------

const DEFAULT_DRAFT_STATE = {
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
  ...DEFAULT_DRAFT_STATE,
  completedArtifacts: [],
  isGenerateDialogOpen: false,
  previewJobId: null,

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

  addCompletedArtifact: (artifact) =>
    set((state) => {
      if (artifact.job_id && state.completedArtifacts.some((a) => a.job_id === artifact.job_id)) {
        return state
      }
      return { completedArtifacts: [artifact, ...state.completedArtifacts] }
    }),

  openGenerateDialog: () => set({ isGenerateDialogOpen: true }),

  closeGenerateDialog: () =>
    set({ isGenerateDialogOpen: false, ...DEFAULT_DRAFT_STATE }),

  setPreviewJobId: (jobId) => set({ previewJobId: jobId }),

  reset: () => set(DEFAULT_DRAFT_STATE),
}))
