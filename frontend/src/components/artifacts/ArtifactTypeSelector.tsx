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
import { ArtifactType } from '@/lib/types/artifacts'
import { useTranslation } from '@/lib/hooks/use-translation'

// Map artifact type IDs to lucide icons and accent colours
const TYPE_ICON_MAP: Record<string, { icon: React.ElementType; color: string }> = {
  briefing:        { icon: Briefcase,    color: 'text-blue-500' },
  faq:             { icon: HelpCircle,   color: 'text-violet-500' },
  flashcards:      { icon: Layers,       color: 'text-amber-500' },
  quiz:            { icon: Brain,        color: 'text-pink-500' },
  study_guide:     { icon: GraduationCap, color: 'text-emerald-500' },
  timeline:        { icon: Calendar,     color: 'text-cyan-500' },
  mindmap:         { icon: GitBranch,    color: 'text-orange-500' },
  slide_deck:      { icon: Presentation, color: 'text-indigo-500' },
  pitch_deck:      { icon: Presentation, color: 'text-purple-500' },
  research_review: { icon: FlaskConical, color: 'text-red-500' },
  paper_figure:    { icon: BarChart2,    color: 'text-teal-500' },
  infographic:     { icon: ImageIcon,    color: 'text-lime-500' },
  video_overview:  { icon: Video,        color: 'text-rose-500' },
  data_tables:     { icon: Table2,       color: 'text-sky-500' },
}

const DEFAULT_TYPE_META = { icon: BookOpen, color: 'text-muted-foreground' }

interface ArtifactTypeSelectorProps {
  types: ArtifactType[]
  selected: string | null
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
      {types.map((type) => {
        const meta = TYPE_ICON_MAP[type.id] ?? DEFAULT_TYPE_META
        const Icon = meta.icon
        const isSelected = selected === type.id

        return (
          <button
            key={type.id}
            role="radio"
            aria-checked={isSelected}
            disabled={disabled}
            onClick={() => onSelect(type)}
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
              {type.label}
            </span>
            <span className="text-[11px] leading-snug text-muted-foreground line-clamp-2">
              {type.description}
            </span>
          </button>
        )
      })}
    </div>
  )
}
