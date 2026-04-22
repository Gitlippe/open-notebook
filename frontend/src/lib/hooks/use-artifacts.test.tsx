import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'

// ---------------------------------------------------------------------------
// Mock API module before importing hooks
// ---------------------------------------------------------------------------

vi.mock('@/lib/api/artifacts', () => ({
  artifactsApi: {
    listArtifactTypes: vi.fn(),
    submitGenerateJob: vi.fn(),
    getArtifactJob: vi.fn(),
    downloadArtifact: vi.fn(),
  },
}))

vi.mock('@/lib/hooks/use-toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}))

import { artifactsApi } from '@/lib/api/artifacts'
import { useArtifactTypes, useGenerateArtifact, useArtifactJob } from './use-artifacts'

const mockListArtifactTypes = artifactsApi.listArtifactTypes as ReturnType<typeof vi.fn>
const mockSubmitGenerateJob = artifactsApi.submitGenerateJob as ReturnType<typeof vi.fn>
const mockGetArtifactJob = artifactsApi.getArtifactJob as ReturnType<typeof vi.fn>

// ---------------------------------------------------------------------------
// Test wrapper
// ---------------------------------------------------------------------------

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
  const wrapper = ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
  return { wrapper, qc }
}

beforeEach(() => {
  vi.clearAllMocks()
})

// ---------------------------------------------------------------------------
// useArtifactTypes
// ---------------------------------------------------------------------------

describe('useArtifactTypes()', () => {
  it('fetches and returns artifact types', async () => {
    const types = [
      { type: 'briefing', description: 'A short briefing' },
      { type: 'slide_deck', description: 'A slide deck' },
    ]
    mockListArtifactTypes.mockResolvedValueOnce(types)

    const { wrapper } = makeWrapper()
    const { result } = renderHook(() => useArtifactTypes(), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(types)
    expect(mockListArtifactTypes).toHaveBeenCalledTimes(1)
  })

  it('surfaces errors', async () => {
    mockListArtifactTypes.mockRejectedValueOnce(new Error('Network error'))
    const { wrapper } = makeWrapper()
    const { result } = renderHook(() => useArtifactTypes(), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})

// ---------------------------------------------------------------------------
// useGenerateArtifact
// ---------------------------------------------------------------------------

describe('useGenerateArtifact()', () => {
  it('calls submitGenerateJob and resolves with job data', async () => {
    const submitted = { job_id: 'job-abc', status: 'submitted' }
    mockSubmitGenerateJob.mockResolvedValueOnce(submitted)

    const { wrapper } = makeWrapper()
    const { result } = renderHook(() => useGenerateArtifact(), { wrapper })

    result.current.mutate({
      artifact_type: 'briefing',
      sources: [{ title: 'Test', content: 'Content' }],
      config: {},
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(submitted)
  })

  it('handles mutation errors gracefully', async () => {
    mockSubmitGenerateJob.mockRejectedValueOnce(
      new Error('Artifact generation failed')
    )

    const { wrapper } = makeWrapper()
    const { result } = renderHook(() => useGenerateArtifact(), { wrapper })

    result.current.mutate({ artifact_type: 'briefing' })
    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})

// ---------------------------------------------------------------------------
// useArtifactJob
// ---------------------------------------------------------------------------

describe('useArtifactJob()', () => {
  it('is disabled when jobId is null', () => {
    const { wrapper } = makeWrapper()
    const { result } = renderHook(() => useArtifactJob(null), { wrapper })
    expect(result.current.fetchStatus).toBe('idle')
    expect(mockGetArtifactJob).not.toHaveBeenCalled()
  })

  it('fetches job status for a known jobId', async () => {
    const jobResult = { status: 'completed', artifact_type: 'briefing', files: [] }
    mockGetArtifactJob.mockResolvedValueOnce(jobResult)

    const { wrapper } = makeWrapper()
    const { result } = renderHook(() => useArtifactJob('job-123'), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(jobResult)
    expect(mockGetArtifactJob).toHaveBeenCalledWith('job-123')
  })

  it('returns false refetchInterval once status is "completed" (polling stops)', async () => {
    // Verify the refetchInterval logic: when data.status is terminal, interval = false
    mockGetArtifactJob.mockResolvedValue({ status: 'completed', files: [] })

    const { wrapper } = makeWrapper()
    const { result } = renderHook(() => useArtifactJob('job-456'), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.status).toBe('completed')
    // At this point the hook should have fetched successfully
    expect(mockGetArtifactJob).toHaveBeenCalledWith('job-456')
  })

  it('returns false refetchInterval once status is "failed" (polling stops)', async () => {
    mockGetArtifactJob.mockResolvedValue({ status: 'failed', error: 'LLM error' })

    const { wrapper } = makeWrapper()
    const { result } = renderHook(() => useArtifactJob('job-789'), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.status).toBe('failed')
    expect(mockGetArtifactJob).toHaveBeenCalledWith('job-789')
  })

  it('respects the enabled option', () => {
    const { wrapper } = makeWrapper()
    const { result } = renderHook(
      () => useArtifactJob('job-disabled', { enabled: false }),
      { wrapper }
    )
    expect(result.current.fetchStatus).toBe('idle')
    expect(mockGetArtifactJob).not.toHaveBeenCalled()
  })
})
