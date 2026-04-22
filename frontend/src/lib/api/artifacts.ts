import apiClient from './client'
import {
  ArtifactType,
  ArtifactGenerateRequest,
  ArtifactJobSubmitted,
  ArtifactJobResult,
} from '@/lib/types/artifacts'

/**
 * List all registered artifact types.
 * GET /api/artifacts/types
 */
export async function listArtifactTypes(): Promise<ArtifactType[]> {
  const response = await apiClient.get<{ types: ArtifactType[] }>('/artifacts/types')
  return response.data.types
}

/**
 * Submit an artifact generation job to the async queue.
 * POST /api/artifacts/generate
 * Returns immediately with a job_id to poll.
 */
export async function submitGenerateJob(
  request: ArtifactGenerateRequest
): Promise<ArtifactJobSubmitted> {
  const response = await apiClient.post<ArtifactJobSubmitted>(
    '/artifacts/generate',
    request
  )
  return response.data
}

/**
 * Poll the status of an artifact generation job.
 * GET /api/artifacts/jobs/{job_id}
 */
export async function getArtifactJob(jobId: string): Promise<ArtifactJobResult> {
  const response = await apiClient.get<ArtifactJobResult>(
    `/artifacts/jobs/${jobId}`
  )
  return response.data
}

/**
 * Download a generated artifact file.
 * GET /api/artifacts/download?path=<abs>
 * Returns the raw Blob so callers can trigger a browser download.
 */
export async function downloadArtifact(path: string): Promise<Blob> {
  const response = await apiClient.get<Blob>('/artifacts/download', {
    params: { path },
    responseType: 'blob',
  })
  return response.data
}

export const artifactsApi = {
  listArtifactTypes,
  submitGenerateJob,
  getArtifactJob,
  downloadArtifact,
}
