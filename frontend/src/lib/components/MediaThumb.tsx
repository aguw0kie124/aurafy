import { Music2, UserRound } from 'lucide-react';
import styles from './MediaThumb.module.css';

export default function MediaThumb({
	src = null,
	alt,
	kind,
	size = 'medium',
	round = false,
	label = ''
}: {
	src?: string | null;
	alt: string;
	kind: 'artist' | 'cover';
	size?: 'small' | 'medium' | 'large';
	round?: boolean;
	label?: string;
}) {
	const initials = label.trim().slice(0, 2).toUpperCase();

	return (
		<span className={`${styles.thumb} ${styles[size]}${round ? ` ${styles.round}` : ''}`}>
			{src ? (
				<img src={src} alt={alt} />
			) : initials ? (
				<strong aria-hidden="true">{initials}</strong>
			) : kind === 'artist' ? (
				<UserRound aria-hidden="true" />
			) : (
				<Music2 aria-hidden="true" />
			)}
		</span>
	);
}
