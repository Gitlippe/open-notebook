'use client'

import {
  BookOpen,
  HelpCircle,
  Layers,
  Brain,
  Calendar,
  GitBranch,
  Presentation,
  Briefcase,
  FlaskConical,
  BarChart2,
  ImageIcon,
  Video,
  Table2,
  GraduationCap,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { ArtifactType, ArtifactTypeId } from '@/lib/types/artifacts'
import { useTranslation } from '@/lib/hooks/use-translation'

// Map artifact type IDs to lucide icons and accent colours
const TYPE_META: Record<ArtifactTypeId | string, { icon: React.ElementType; color: string; label: string }> = {
  briefing:        { icon: Briefcase,     color: 'text-blue-500',    label: 'Briefing' },
  faq:             { icon: HelpCircle,    color: 'text-violet-500',  label: 'FAQ' },
  flashcards:      { icon: Layers,        color: 'text-amber-500',   label: 'Flashcards' },
  quiz:            { icon: Brain,         color: 'text-pink-500',    label: 'Quiz' },
  study_guide:     { icon: GraduationCap, color: 'text-emerald-500', label: 'Study Guide' },
  timeline:        { icon: Calendar,      color: 'text-cyan-500',    label: 'Timeline' },
  mindmap:         { icon: GitBranch,     color: 'text-orange-500',  label: 'Mindmap' },
  slide_deck:      { icon: Presentation,  color: 'text-indigo-500',  label: 'Slide Deck' },
  pitch_deck:      { icon: Presentation,  color: 'text-purple-500',  label: 'Pitch Deck' },
  research_review: { icon: FlaskConical,  color: 'text-red-500',     label: 'Research Review' },
  paper_figure:    { icon: BarChart2,     color: 'text-teal-500',    label: 'Paper Figure' },
  infographic:     { icon: ImageIcon,     color: 'text-lime-500',    label: 'Infographic' },
  video_overview:  { icon: Video,         color: 'text-rose-500',    label: 'Video Overview' },
  data_tables:     { icon: Table2,        color: 'text-sky-500',     label: 'Data Tables' },
}

const DEFAULT_META = { icon: BookOpen, color: 'text-muted-foreground', label: '' }

interface ArtifactTypeSelectorProps {
  types: ArtifactType[]
  selected: ArtifactTypeId | string | null
  onSelect: (type: ArtifactType) => void
  disabled?: boolean
}

export function ArtifactTypeSelector({
  types,
  selected,
  onSelect,
  disabled = false,
}: ArtifactTypeSelectorProps) {
  const { t } = useTranslation()

  if (types.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-4 text-center">
        {t('common.loading')}
      </p>
    )
  }

  return (
    <div
      role="radiogroup"
      aria-label={t('artifacts.pickType')}
      className="grid grid-cols-2 gap-2 sm:grid-cols-3"
    >
      {types.map((artifactType) => {
        const meta = TYPE_META[artifactType.type] ?? DEFAULT_META
        const Icon = meta.icon
        const isSelected = selected === artifactType.type

        return (
          <button
            key={artifactType.type}
            role="radio"
            aria-checked={isSelected}
            disabled={disabled}
            onClick={() => onSelect(artifactType)}
            className={cn(
              'group flex flex-col gap-1.5 rounded-lg border p-3 text-left transition-all',
              'hover:bg-accent hover:border-accent-foreground/20',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              'disabled:pointer-events-none disabled:opacity-50',
              isSelected
                ? 'border-primary bg-primary/5 ring-1 ring-primary'
                : 'border-border bg-card'
            )}
          >
            <Icon
              className={cn('h-5 w-5 shrink-0', meta.color)}
              aria-hidden="true"
            />
            <span className="text-xs font-semibold leading-tight text-foreground">
              {meta.label || artifactType.type.replace(/_/g, ' ')}
            </span>
            <span className="text-[11px] leading-snug text-muted-foreground line-clamp-2">
              {artifactType.description}
            </span>
          </button>
        )
      })}
    </div>
  )
}
