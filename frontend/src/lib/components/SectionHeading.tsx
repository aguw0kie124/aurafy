import styles from './SectionHeading.module.css';

export default function SectionHeading({ title, subtitle }: { title: string; subtitle?: string }) {
	return (
		<div className={styles.sectionHeading}>
			<h1>{title}</h1>
			{subtitle && <p>{subtitle}</p>}
		</div>
	);
}
