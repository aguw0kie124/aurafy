import styles from './EmptyState.module.css';

export default function EmptyState({
	title,
	compact = false
}: {
	title: string;
	compact?: boolean;
}) {
	return (
		<div className={`${styles.emptyState}${compact ? ` ${styles.compact}` : ''}`}>
			<span>{title}</span>
		</div>
	);
}
