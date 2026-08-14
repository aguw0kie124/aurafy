import { rangeOptions, type StatsRangeValue } from '@/lib/data/music';
import styles from './RangeTabs.module.css';

export default function RangeTabs({
	active = 'short_term',
	options = rangeOptions,
	onSelect = () => {}
}: {
	active?: StatsRangeValue;
	options?: { label: string; value: StatsRangeValue }[];
	onSelect?: (range: StatsRangeValue) => void | Promise<void>;
}) {
	return (
		<div className={styles.rangeTabs} aria-label="Time range">
			{options.map((option) => (
				<button
					key={option.value}
					type="button"
					className={option.value === active ? styles.active : undefined}
					onClick={() => onSelect(option.value)}
				>
					{option.label}
				</button>
			))}
		</div>
	);
}
