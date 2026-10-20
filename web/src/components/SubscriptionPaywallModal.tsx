import { Link } from 'react-router-dom'
import { Button } from './Button'
import { Modal } from './Modal'
import type { SubscriptionPlanOption } from '../lib/types'

const PLAN_LABELS: Record<SubscriptionPlanOption['plan'], string> = {
  monthly: 'Monthly',
  semiannual: 'Semi-annual',
  annual: 'Annual',
}

export function SubscriptionPaywallModal({
  open,
  onClose,
  plans = [],
}: {
  open: boolean
  onClose: () => void
  plans?: SubscriptionPlanOption[]
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Seller subscription required"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Back
          </Button>
          <Link to="/marketplace/subscription" className="btn btn--primary">
            Choose a plan
          </Link>
        </>
      }
    >
      <p>
        Publishing equipment on STAR Marketplace requires an active seller
        subscription. It lets you:
      </p>
      <ul className="paywall-list">
        <li>Publish and manage equipment listings</li>
        <li>Manage descriptions, prices and inventory</li>
        <li>Follow buyer orders and fulfil them</li>
      </ul>
      <p className="field__hint">
        Monthly plan from 2 500 FCFA for a first month (then 5 000 FCFA/month;
        10 000 for 6 months; 12 000 for 12 months). Payment is confirmed by the
        server before any listing is published.
      </p>
      {plans.length > 0 && (
        <div className="badge-row">
          {plans.map((plan) => (
            <span className="badge badge--neutral" key={plan.plan}>
              {PLAN_LABELS[plan.plan]} · {plan.price_fcfa} FCFA
            </span>
          ))}
        </div>
      )}
    </Modal>
  )
}
