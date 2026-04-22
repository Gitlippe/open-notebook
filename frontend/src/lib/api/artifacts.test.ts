import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  listArtifactTypes,
  submitGenerateJob,
  getArtifactJob,
  downloadArtifact,
} from './artifacts'
import apiClient from './client'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

const mockGet = apiClient.get as ReturnType<typeof vi.fn>
const mockPost = apiClient.post as ReturnType<typeof vi.fn>

beforeEach(() => {
  vi.clearAllMocks()
})

// ---------------------------------------------------------------------------
// listArtifactTypes
// ---------------------------------------------------------------------------

describe('listArtifactTypes()', () => {
  it('calls GET /artifacts/types and returns the types array', async () => {
    const types = [
      { type: 'briefing', description: 'A short briefing' },
      { type: 'slide_deck', description: 'A slide deck' },
    ]
    mockGet.mockResolvedValueOnce({ data: { types } })

    const result = await listArtifactTypes()

    expect(mockGet).toHaveBeenCalledWith('/artifacts/types')
    expect(result).toEqual(types)
  })

  it('propagates network errors', async () => {
    mockGet.mockRejectedValueOnce(new Error('Network error'))
    await expect(listArtifactTypes()).rejects.toThrow('Network error')
  })
})

// ---------------------------------------------------------------------------
// submitGenerateJob
// ---------------------------------------------------------------------------

describe('submitGenerateJob()', () => {
  it('calls POST /artifacts/generate with the request body', async () => {
    const submitted = { job_id: 'job-123', status: 'submitted' }
    mockPost.mockResolvedValueOnce({ data: submitted })

    const request = {
      artifact_type: 'briefing' as const,
      sources: [{ title: 'Test', content: 'Content' }],
      config: {},
    }
    const result = await submitGenerateJob(request)

    expect(mockPost).toHaveBeenCalledWith('/artifacts/generate', request)
    expect(result).toEqual(submitted)
  })

  it('propagates API errors for invalid artifact types', async () => {
    const axiosError = {
      response: { data: { detail: 'Unknown artifact type' }, status: 422 },
      message: 'Request failed with status code 422',
    }
    mockPost.mockRejectedValueOnce(axiosError)

    await expect(
      submitGenerateJob({ artifact_type: 'invalid_type' })
    ).rejects.toMatchObject({ response: { status: 422 } })
  })
})

// ---------------------------------------------------------------------------
// getArtifactJob
// ---------------------------------------------------------------------------

describe('getArtifactJob()', () => {
  it('calls GET /artifacts/jobs/{jobId}', async () => {
    const jobResult = {
      status: 'completed',
      artifact_type: 'briefing',
      files: [{ path: '/output/briefing.md', mime_type: 'text/markdown' }],
    }
    mockGet.mockResolvedValueOnce({ data: jobResult })

    const result = await getArtifactJob('job-123')

    expect(mockGet).toHaveBeenCalledWith('/artifacts/jobs/job-123')
    expect(result).toEqual(jobResult)
  })

  it('returns running status for in-progress jobs', async () => {
    mockGet.mockResolvedValueOnce({ data: { status: 'running' } })
    const result = await getArtifactJob('job-456')
    expect(result.status).toBe('running')
  })

  it('propagates 404 for unknown job IDs', async () => {
    const notFound = {
      response: { status: 404, data: { detail: 'Not found' } },
    }
    mockGet.mockRejectedValueOnce(notFound)
    await expect(getArtifactJob('unknown')).rejects.toMatchObject({
      response: { status: 404 },
    })
  })
})

// ---------------------------------------------------------------------------
// downloadArtifact
// ---------------------------------------------------------------------------

describe('downloadArtifact()', () => {
  it('calls GET /artifacts/download with path as query param and blob responseType', async () => {
    const blob = new Blob(['data'], { type: 'text/markdown' })
    mockGet.mockResolvedValueOnce({ data: blob })

    const result = await downloadArtifact('/output/briefing.md')

    expect(mockGet).toHaveBeenCalledWith('/artifacts/download', {
      params: { path: '/output/briefing.md' },
      responseType: 'blob',
    })
    expect(result).toBe(blob)
  })
})
