'use client'

import { useState } from 'react'
import { Sparkles, Plus } from 'lucide-react'

import { AppShell } from '@/components/layout/AppShell'
import { Button } from '@/components/ui/button'
import { ArtifactCard } from '@/components/artifacts/ArtifactCard'
import { ArtifactPreview } from '@/components/artifacts/ArtifactPreview'
import { GenerateArtifactDialog } from '@/components/artifacts/GenerateArtifactDialog'
import { useArtifactsStore } from '@/lib/stores/artifacts-store'
import { useTranslation } from '@/lib/hooks/use-translation'
import type { ArtifactJobResult } from '@/lib/types/artifacts'

const ARTIFACT_TYPE_COUNT = 14

export default function ArtifactsPage() {
  const { t } = useTranslation()
  const {
    completedArtifacts,
    isGenerateDialogOpen,
    openGenerateDialog,
    closeGenerateDialog,
    setPreviewJobId,
    addCompletedArtifact,
  } = useArtifactsStore()

  const [previewArtifact, setPreviewArtifact] = useState<ArtifactJobResult | null>(null)

  const handleOpenPreview = (artifact: ArtifactJobResult) => {
    setPreviewArtifact(artifact)
    setPreviewJobId(artifact.job_id)
  }

  const handleClosePreview = () => {
    setPreviewArtifact(null)
    setPreviewJobId(null)
  }

  const handleArtifactReady = (artifact: ArtifactJobResult) => {
    // addCompletedArtifact is idempotent (checks by job_id)
    addCompletedArtifact(artifact)
  }

  return (
    <AppShell>
      <div className="flex-1 overflow-y-auto">
        <div className="px-6 py-6 space-y-6">
          {/* Page header */}
          <header className="flex items-start justify-between gap-4">
            <div className="space-y-1">
              <h1 className="text-2xl font-semibold tracking-tight">
                {t('artifacts.title')}
              </h1>
              <p className="text-muted-foreground text-sm">
                {t('artifacts.pageDesc')}
              </p>
            </div>

            <Button onClick={openGenerateDialog} size="sm" className="gap-2 shrink-0">
              <Plus className="h-4 w-4" />
              {t('artifacts.newArtifact')}
            </Button>
          </header>

          {/* Content */}
          {completedArtifacts.length === 0 ? (
            /* Empty state */
            <div className="flex flex-col items-center justify-center gap-4 rounded-xl border-2 border-dashed border-border py-16 text-center">
              <div className="rounded-full bg-muted p-4">
                <Sparkles className="h-8 w-8 text-muted-foreground" />
              </div>
              <div className="space-y-1 max-w-sm">
                <h2 className="text-base font-semibold">{t('artifacts.noArtifactsYet')}</h2>
                <p className="text-sm text-muted-foreground">
                  {t('artifacts.noArtifactsHint').replace(
                    '{count}',
                    String(ARTIFACT_TYPE_COUNT)
                  )}
                </p>
              </div>
              <Button onClick={openGenerateDialog} size="sm" className="gap-2 mt-2">
                <Plus className="h-4 w-4" />
                {t('artifacts.newArtifact')}
              </Button>
            </div>
          ) : (
            /* Artifact grid */
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {completedArtifacts.map((artifact) => (
                <ArtifactCard
                  key={artifact.job_id}
                  artifact={artifact}
                  onOpenPreview={handleOpenPreview}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Generate dialog */}
      <GenerateArtifactDialog
        open={isGenerateDialogOpen}
        onClose={closeGenerateDialog}
        onArtifactReady={handleArtifactReady}
      />

      {/* Preview modal */}
      <ArtifactPreview
        artifact={previewArtifact}
        open={Boolean(previewArtifact)}
        onClose={handleClosePreview}
      />
    </AppShell>
  )
}
