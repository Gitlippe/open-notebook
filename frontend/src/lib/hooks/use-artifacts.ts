import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { artifactsApi } from '@/lib/api/artifacts'
import { useToast } from '@/lib/hooks/use-toast'
import { useTranslation } from '@/lib/hooks/use-translation'
import { getApiErrorKey } from '@/lib/utils/error-handler'
import {
  ArtifactGenerateRequest,
  ArtifactJobResult,
  TERMINAL_ARTIFACT_STATUSES,
} from '@/lib/types/artifacts'

// ---------------------------------------------------------------------------
// Query-key extensions for artifacts (not in shared QUERY_KEYS to avoid
// touching the shared file — see Stream H file-ownership constraints)
// ---------------------------------------------------------------------------

const ARTIFACT_QUERY_KEYS = {
  artifactTypes: ['artifact-types'] as const,
  artifactJobs: ['artifact-jobs'] as const,
  artifactJob: (jobId: string) => ['artifact-jobs', jobId] as const,
} as const

// Re-export so Stream I can import from one place if needed
export { ARTIFACT_QUERY_KEYS }

// ---------------------------------------------------------------------------
// useArtifactTypes
// ---------------------------------------------------------------------------

/**
 * Fetch the list of all registered artifact types.
 * staleTime: Infinity — types are static for the lifetime of the server process.
 */
export function useArtifactTypes() {
  return useQuery({
    queryKey: ARTIFACT_QUERY_KEYS.artifactTypes,
    queryFn: artifactsApi.listArtifactTypes,
    staleTime: Infinity,
  })
}

// ---------------------------------------------------------------------------
// useGenerateArtifact
// ---------------------------------------------------------------------------

/**
 * Submit an artifact generation job.
 * On success, invalidates the artifact-jobs list so any polling hooks re-fetch.
 */
export function useGenerateArtifact() {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const { t } = useTranslation()

  return useMutation({
    mutationFn: (payload: ArtifactGenerateRequest) =>
      artifactsApi.submitGenerateJob(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ARTIFACT_QUERY_KEYS.artifactJobs })
      toast({
        title: t('artifacts.generationStarted'),
        description: t('artifacts.generationStartedDesc'),
      })
    },
    onError: (error: unknown) => {
      toast({
        title: t('artifacts.failedToStartGeneration'),
        description: getApiErrorKey(error, t('common.error')),
        variant: 'destructive',
      })
    },
  })
}

// ---------------------------------------------------------------------------
// useArtifactJob
// ---------------------------------------------------------------------------

export interface UseArtifactJobOptions {
  /** Override the default poll interval (ms). Pass false to disable polling. */
  refetchInterval?: number | false
  /** Set to false to skip the query entirely (e.g. when jobId is unknown). */
  enabled?: boolean
}

/**
 * Poll the status of an artifact generation job.
 *
 * Polling behaviour:
 * - Polls every 2 seconds while the job is in a non-terminal status.
 * - Stops automatically when status is 'completed' or 'failed'.
 */
export function useArtifactJob(
  jobId: string | null | undefined,
  options?: UseArtifactJobOptions
) {
  const { enabled = true } = options ?? {}

  return useQuery<ArtifactJobResult>({
    queryKey: ARTIFACT_QUERY_KEYS.artifactJob(jobId ?? ''),
    queryFn: () => artifactsApi.getArtifactJob(jobId!),
    enabled: enabled && !!jobId,
    refetchInterval: (current) => {
      // Allow caller override
      if (options?.refetchInterval !== undefined) {
        return options.refetchInterval
      }

      const data = current.state.data as ArtifactJobResult | undefined
      if (!data) {
        // No data yet — keep polling
        return 2000
      }

      // Stop polling once we reach a terminal state
      return TERMINAL_ARTIFACT_STATUSES.includes(data.status) ? false : 2000
    },
  })
}
