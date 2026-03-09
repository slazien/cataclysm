import '@testing-library/jest-dom/vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { EquipmentInterstitial } from '../EquipmentInterstitial';

// Mock hooks
const mockCreateProfile = vi.fn();
const mockAssignEquipment = vi.fn();
const mockVehicleSearch = vi.fn(() => ({ data: [], isLoading: false }));
const mockEquipmentProfiles = vi.fn(() => ({ data: { items: [] }, isLoading: false }));

vi.mock('@/hooks/useEquipment', () => ({
  useCreateProfile: () => ({ mutateAsync: mockCreateProfile, isPending: false }),
  useAssignEquipment: () => ({ mutateAsync: mockAssignEquipment, isPending: false }),
  useVehicleSearch: (q: string) => mockVehicleSearch(q),
  useEquipmentProfiles: () => mockEquipmentProfiles(),
}));

vi.mock('@/lib/api', () => ({
  getVehicleSpec: vi.fn(),
}));

vi.mock('motion/react', () => ({
  motion: {
    div: ({ children, ...rest }: React.HTMLAttributes<HTMLDivElement>) => <div {...rest}>{children}</div>,
    ul: ({ children, ...rest }: React.HTMLAttributes<HTMLUListElement>) => <ul {...rest}>{children}</ul>,
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('lucide-react', () => ({
  Search: () => <svg data-testid="icon-search" />,
  X: () => <svg data-testid="icon-x" />,
  CheckCircle2: () => <svg data-testid="icon-check" />,
}));

describe('EquipmentInterstitial', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockVehicleSearch.mockReturnValue({ data: [], isLoading: false });
    mockEquipmentProfiles.mockReturnValue({ data: { items: [] }, isLoading: false });
  });

  it('renders the heading and skip button', () => {
    render(<EquipmentInterstitial sessionId="sess-1" onComplete={vi.fn()} />);
    expect(screen.getByText(/what are you driving/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /skip for now/i })).toBeInTheDocument();
  });

  it('calls onComplete when skip is clicked', () => {
    const onComplete = vi.fn();
    render(<EquipmentInterstitial sessionId="sess-1" onComplete={onComplete} />);
    fireEvent.click(screen.getByRole('button', { name: /skip for now/i }));
    expect(onComplete).toHaveBeenCalledOnce();
  });

  it('Save & Continue button is disabled when tire size and compound are empty', () => {
    render(<EquipmentInterstitial sessionId="sess-1" onComplete={vi.fn()} />);
    expect(screen.getByRole('button', { name: /save.*continue/i })).toBeDisabled();
  });

  it('Save & Continue becomes enabled when compound and tire size are filled', () => {
    render(<EquipmentInterstitial sessionId="sess-1" onComplete={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /^street$/i }));
    fireEvent.change(screen.getByPlaceholderText(/e\.g\. 205/i), { target: { value: '205/50R16' } });
    expect(screen.getByRole('button', { name: /save.*continue/i })).not.toBeDisabled();
  });

  it('shows existing profiles as quick-pick when available', () => {
    mockEquipmentProfiles.mockReturnValue({
      data: {
        items: [
          {
            id: 'p1',
            name: 'Miata – Street',
            tires: { model: 'RE-71RS', compound_category: 'track/r-compound', size: '205/50R16', estimated_mu: 1.1, mu_source: 'curated', mu_confidence: 'high', treadwear_rating: null, pressure_psi: null, brand: null, age_sessions: null },
            is_default: true,
          },
        ],
      },
      isLoading: false,
    });
    render(<EquipmentInterstitial sessionId="sess-1" onComplete={vi.fn()} />);
    expect(screen.getByText('Miata – Street')).toBeInTheDocument();
    expect(screen.getByText(/use existing setup/i)).toBeInTheDocument();
  });

  it('assigns existing profile and calls onComplete on quick-pick click', async () => {
    mockEquipmentProfiles.mockReturnValue({
      data: {
        items: [
          {
            id: 'p1',
            name: 'Miata – Street',
            tires: { model: 'RE-71RS', compound_category: 'track/r-compound', size: '205/50R16', estimated_mu: 1.1, mu_source: 'curated', mu_confidence: 'high', treadwear_rating: null, pressure_psi: null, brand: null, age_sessions: null },
            is_default: true,
          },
        ],
      },
      isLoading: false,
    });
    mockAssignEquipment.mockResolvedValue({});
    const onComplete = vi.fn();
    render(<EquipmentInterstitial sessionId="sess-1" onComplete={onComplete} />);
    fireEvent.click(screen.getByText('Miata – Street'));
    await waitFor(() =>
      expect(mockAssignEquipment).toHaveBeenCalledWith({
        sessionId: 'sess-1',
        body: { profile_id: 'p1' },
      }),
    );
    expect(onComplete).toHaveBeenCalled();
  });

  it('shows vehicle search results when query matches', async () => {
    mockVehicleSearch.mockReturnValue({
      data: [
        { slug: 'mazda_miata_nd', make: 'Mazda', model: 'MX-5 Miata', generation: 'ND', hp: 181, weight_kg: 1050, drivetrain: 'RWD' },
      ],
      isLoading: false,
    });
    render(<EquipmentInterstitial sessionId="sess-1" onComplete={vi.fn()} />);
    fireEvent.change(screen.getByPlaceholderText(/search vehicle/i), { target: { value: 'Miata' } });
    await waitFor(() => expect(screen.getByText(/MX-5 Miata/)).toBeInTheDocument());
    expect(screen.getByText(/181hp/)).toBeInTheDocument();
  });
});
