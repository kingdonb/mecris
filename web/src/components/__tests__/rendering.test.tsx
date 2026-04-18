import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import MomentumVisualizer from '../MomentumVisualizer'
import Odometer from '../Odometer'
import ReviewPump from '../ReviewPump'
import type { LanguageStat } from '../../types/mecris'

describe('Component Rendering', () => {
  it('renders MomentumVisualizer without crashing', () => {
    render(<MomentumVisualizer momentum={0.8} />)
    // Basic existence check
    const container = document.querySelector('.momentum-wrapper')
    expect(container).toBeInTheDocument()
  })

  it('renders Odometer with correct label and value', () => {
    render(<Odometer value={20.91} label="VIRTUAL BUDGET" />)
    expect(screen.getByText('VIRTUAL BUDGET')).toBeInTheDocument()
    // It should render digits
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getAllByText('0').length).toBeGreaterThan(0)
    expect(screen.getByText('.')).toBeInTheDocument()
    expect(screen.getByText('9')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
  })

  it('renders ReviewPump with language data', () => {
    const stat: LanguageStat = {
      name: 'Arabic',
      current: 1762,
      tomorrow: 45,
      next_7_days: 315,
      daily_rate: 10,
      safebuf: 10,
      derail_risk: 'low',
      pump_multiplier: 2.0,
      has_goal: true,
      daily_completions: 0,
      target_flow_rate: 170,
      absolute_target: 170,
      goal_met: false
    }
    render(<ReviewPump stat={stat} onMultiplierChange={() => {}} />)
    expect(screen.getByText('ARABIC')).toBeInTheDocument()
    expect(screen.getByText('DEBT: 1762 CARDS')).toBeInTheDocument()
    expect(screen.getByText('STEADY')).toBeInTheDocument()
  })
})
