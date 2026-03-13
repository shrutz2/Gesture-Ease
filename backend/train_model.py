import numpy as np
import tensorflow as tf
from tensorflow.keras import layers, models, optimizers, callbacks
from tensorflow.keras.regularizers import l1_l2
from tensorflow.keras.utils import to_categorical
from sklearn.utils.class_weight import compute_class_weight
from sklearn.metrics import classification_report, confusion_matrix
import pickle
import json
import logging
from pathlib import Path   
import argparse
from datetime import datetime
import os
import matplotlib.pyplot as plt
import seaborn as sns

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Reproducibility
SEED = 42
np.random.seed(SEED)
tf.random.set_seed(SEED)
os.environ['PYTHONHASHSEED'] = str(SEED)

# Configuration
SEQUENCE_LENGTH = 30
FEATURE_DIM = 126
LEARNING_RATE = 0.001
BATCH_SIZE = 32
MAX_EPOCHS = 150

class FixedSignLanguageTrainer:
    """Fixed trainer that will definitely work"""
    
    def __init__(self, config):
        self.config = config
        self.model = None
        self.history = None 
         
        # Create directories
        self.models_dir = Path(config.get('models_dir', 'models'))
        self.experiments_dir = Path(config.get('experiments_dir', 'experiments'))
        self.models_dir.mkdir(exist_ok=True)
        self.experiments_dir.mkdir(exist_ok=True)
        
    def build_simple_model(self, num_classes):
        """Build simple but effective model - guaranteed to work"""
        logger.info(f"[BUILDING_CONSTRUCTION] Building simple effective model for {num_classes} classes...")
        
        model = models.Sequential([
            # Input
            layers.Input(shape=(SEQUENCE_LENGTH, FEATURE_DIM)),
            
            # Bidirectional LSTM layers
            layers.Bidirectional(layers.LSTM(
                128, return_sequences=True,
                dropout=0.3, recurrent_dropout=0.2
            )),
            layers.BatchNormalization(),
            
            layers.Bidirectional(layers.LSTM(
                64, return_sequences=False,  # Don't return sequences for the last LSTM
                dropout=0.3, recurrent_dropout=0.2
            )),
            layers.BatchNormalization(),
            
            # Dense layers with strong regularization
            layers.Dense(256, activation='relu'),
            layers.BatchNormalization(),
            layers.Dropout(0.5),
            
            layers.Dense(128, activation='relu'),
            layers.Dropout(0.4),
            
            layers.Dense(64, activation='relu'),
            layers.Dropout(0.3),
            
            # Output layer
            layers.Dense(num_classes, activation='softmax')
        ])
        
        # Compile
        model.compile(
            optimizer=optimizers.Adam(learning_rate=LEARNING_RATE),
            loss='categorical_crossentropy',
            metrics=[
                'accuracy',
                tf.keras.metrics.TopKCategoricalAccuracy(k=3, name='top3_accuracy'),
                tf.keras.metrics.TopKCategoricalAccuracy(k=5, name='top5_accuracy')
            ]
        )
        
        self.model = model
        logger.info(f"[CHECK] Simple model built with {model.count_params():,} parameters")
        return model
    
    def build_advanced_model(self, num_classes):
        """Build advanced model with proper attention using Functional API"""
        logger.info(f" Building advanced model for {num_classes} classes...")
        
        # Input
        inputs = layers.Input(shape=(SEQUENCE_LENGTH, FEATURE_DIM))
        
        # First Bidirectional LSTM
        lstm1 = layers.Bidirectional(layers.LSTM(
            128, return_sequences=True, 
            dropout=0.3, recurrent_dropout=0.2
        ))(inputs)
        lstm1 = layers.BatchNormalization()(lstm1)
        
        # Second Bidirectional LSTM
        lstm2 = layers.Bidirectional(layers.LSTM(
            64, return_sequences=True,
            dropout=0.3, recurrent_dropout=0.2
        ))(lstm1)
        lstm2 = layers.BatchNormalization()(lstm2)
        
        # Attention mechanism
        attention = layers.Dense(1, activation='tanh')(lstm2)
        attention = layers.Flatten()(attention)
        attention = layers.Activation('softmax')(attention)
        attention = layers.RepeatVector(128)(attention)  # 64*2 for bidirectional
        attention = layers.Permute([2, 1])(attention)
        
        # Apply attention to LSTM output
        attended = layers.Multiply()([lstm2, attention])
        attended = layers.Lambda(lambda x: tf.reduce_sum(x, axis=1))(attended)
        
        # Dense layers with regularization
        dense1 = layers.Dense(256, activation='relu')(attended)
        dense1 = layers.BatchNormalization()(dense1)
        dense1 = layers.Dropout(0.5)(dense1)
        
        dense2 = layers.Dense(128, activation='relu')(dense1)
        dense2 = layers.Dropout(0.4)(dense2)
        
        dense3 = layers.Dense(64, activation='relu')(dense2)
        dense3 = layers.Dropout(0.3)(dense3)
        
        # Output layer
        outputs = layers.Dense(num_classes, activation='softmax')(dense3)
        
        # Create model
        model = models.Model(inputs=inputs, outputs=outputs)
        
        # Compile
        model.compile(
            optimizer=optimizers.Adam(learning_rate=LEARNING_RATE),
            loss='categorical_crossentropy',
            metrics=[
                'accuracy',
                tf.keras.metrics.TopKCategoricalAccuracy(k=3, name='top3_accuracy'),
                tf.keras.metrics.TopKCategoricalAccuracy(k=5, name='top5_accuracy')
            ]
        )
        
        self.model = model
        logger.info(f"[CHECK] Advanced model built with {model.count_params():,} parameters")
        return model
    
    def get_callbacks(self):
        """Get training callbacks"""
        run_timestamp = self.config['run_timestamp']
        log_dir = self.experiments_dir / run_timestamp
        log_dir.mkdir(exist_ok=True)
        
        callbacks_list = [
            # Early stopping
            callbacks.EarlyStopping(
                monitor='val_loss',
                patience=20,
                restore_best_weights=True,
                verbose=1
            ),
            
            # Model checkpoint
            callbacks.ModelCheckpoint(
                str(self.models_dir / 'best_model.h5'),
                monitor='val_accuracy',
                save_best_only=True,
                mode='max',
                verbose=1
            ),
            
            # Learning rate reduction
            callbacks.ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.2,
                patience=8,
                min_lr=1e-7,
                verbose=1
            ),
            
            # TensorBoard logging
            callbacks.TensorBoard(
                log_dir=log_dir,
                histogram_freq=1
            ),
            
            # CSV logger
            callbacks.CSVLogger(str(log_dir / 'training_log.csv'))
        ]
        
        return callbacks_list
    
    def train(self, X_train, y_train, X_val, y_val, class_weights):
        """Train the model"""
        logger.info(f"[ROCKET] Starting training for {MAX_EPOCHS} epochs...")
        
        # Convert class weights to the correct format
        class_weight_dict = {i: weight for i, weight in enumerate(class_weights)}
        
        # Get callbacks
        train_callbacks = self.get_callbacks()
        
        # Train the model
        self.history = self.model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=MAX_EPOCHS,
            batch_size=BATCH_SIZE,
            callbacks=train_callbacks,
            class_weight=class_weight_dict,
            verbose=1,
            shuffle=True
        )
        
        logger.info("[CHECK] Training completed!")
        return self.history
    
    def evaluate(self, X_test, y_test, label_encoder):
        """Comprehensive model evaluation"""
        logger.info("[BAR_CHART] Performing evaluation...")
        
        # Load best model
        self.model.load_weights(str(self.models_dir / 'best_model.h5'))
        
        # Evaluate on test set
        test_results = self.model.evaluate(X_test, y_test, verbose=0)
        
        # Get predictions
        y_pred_proba = self.model.predict(X_test, verbose=0)
        y_pred = np.argmax(y_pred_proba, axis=1)
        y_true = np.argmax(y_test, axis=1)
        
        # Calculate metrics
        test_loss = test_results[0]
        test_accuracy = test_results[1]
        top3_accuracy = test_results[2] if len(test_results) > 2 else 0
        top5_accuracy = test_results[3] if len(test_results) > 3 else 0
        
        # Classification report
        class_names = label_encoder.classes_
        report = classification_report(
            y_true, y_pred, 
            target_names=class_names,
            output_dict=True,
            zero_division=0
        )
        
        # Confusion matrix
        cm = confusion_matrix(y_true, y_pred)
        
        results = {
            'test_loss': float(test_loss),
            'test_accuracy': float(test_accuracy),
            'top3_accuracy': float(top3_accuracy),
            'top5_accuracy': float(top5_accuracy),
            'classification_report': report,
            'confusion_matrix': cm.tolist(),
            'num_classes': len(class_names),
            'class_names': class_names.tolist()
        }
        
        logger.info(f"Test Accuracy: {test_accuracy*100:.2f}%")
        logger.info(f"Top-3 Accuracy: {top3_accuracy*100:.2f}%")
        if top5_accuracy > 0:
            logger.info(f"Top-5 Accuracy: {top5_accuracy*100:.2f}%")
        
        # Save confusion matrix plot
        self._save_confusion_matrix_plot(cm, class_names)
        
        return results
    
    def _save_confusion_matrix_plot(self, cm, class_names):
        """Save confusion matrix as a plot"""
        plt.figure(figsize=(12, 10))
        
        # If too many classes, show only top confusions
        if len(class_names) > 20:
            # Show only classes with most samples
            class_sums = cm.sum(axis=1)
            top_indices = np.argsort(class_sums)[-20:]
            cm_subset = cm[np.ix_(top_indices, top_indices)]
            class_names_subset = [class_names[i] for i in top_indices]
            
            sns.heatmap(cm_subset, annot=True, fmt='d', cmap='Blues',
                       xticklabels=class_names_subset, yticklabels=class_names_subset)
            plt.title('Confusion Matrix (Top 20 Classes)')
        else:
            sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                       xticklabels=class_names, yticklabels=class_names)
            plt.title('Confusion Matrix')
        
        plt.xlabel('Predicted')
        plt.ylabel('Actual')
        plt.xticks(rotation=45)
        plt.yticks(rotation=45)
        plt.tight_layout()
        
        plt.savefig(self.models_dir / 'confusion_matrix.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info("Confusion matrix plot saved")
    
    def save_model_artifacts(self, label_encoder):
        """Save all model artifacts"""
        logger.info(" Saving model artifacts...")
        
        # Save the complete model
        self.model.save(str(self.models_dir / 'model.keras'))
        
        # Save model in H5 format for compatibility
        self.model.save(str(self.models_dir / 'model.h5'))
        
        # Save labels mapping
        labels_data = {
            'classes': label_encoder.classes_.tolist(),
            'num_classes': len(label_encoder.classes_),
            'id_to_label': {i: label for i, label in enumerate(label_encoder.classes_)},
            'label_to_id': {label: i for i, label in enumerate(label_encoder.classes_)}
        }
        
        with open(self.models_dir / 'labels.json', 'w') as f:
            json.dump(labels_data, f, indent=2)
        
        logger.info("[CHECK] Model artifacts saved")


def load_data(dataset_dir):
    """Load data from dataset/<word>/*.npy files"""
    from sklearn.preprocessing import LabelEncoder
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import RobustScaler
    
    dataset_path = Path(dataset_dir)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_path}")
    
    logger.info(f"[FLOPPY_DISK] Loading data from {dataset_path}...")
    
    X, y = [], []
    word_dirs = sorted([d for d in dataset_path.iterdir() if d.is_dir()])
    
    for word_dir in word_dirs:
        word = word_dir.name
        npy_files = sorted(word_dir.glob('*.npy'))
        for npy_file in npy_files:
            sequence = np.load(npy_file)
            if sequence.shape == (30, 126):
                X.append(sequence)
                y.append(word)
    
    X = np.array(X, dtype=np.float32)
    logger.info(f"[CHECK] Loaded {len(X)} sequences from {len(word_dirs)} words")
    
    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y)
    num_classes = len(label_encoder.classes_)
    logger.info(f"[BULLSEYE] {num_classes} classes: {label_encoder.classes_.tolist()}")
    
    X_temp, X_test, y_temp, y_test = train_test_split(
        X, y_encoded, test_size=0.15, stratify=y_encoded, random_state=SEED
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_temp, y_temp, test_size=0.176, stratify=y_temp, random_state=SEED
    )
    
    scaler = RobustScaler()
    X_train_flat = X_train.reshape(-1, 126)
    scaler.fit(X_train_flat)
    
    X_train = scaler.transform(X_train_flat).reshape(X_train.shape)
    X_val = scaler.transform(X_val.reshape(-1, 126)).reshape(X_val.shape)
    X_test = scaler.transform(X_test.reshape(-1, 126)).reshape(X_test.shape)
    
    artifacts_dir = Path('artifacts')
    artifacts_dir.mkdir(exist_ok=True)
    
    with open(artifacts_dir / 'scaler.pkl', 'wb') as f:
        pickle.dump(scaler, f)
    
    with open(artifacts_dir / 'label_encoder.pkl', 'wb') as f:
        pickle.dump(label_encoder, f)
    
    labels_data = {
        'class_names': label_encoder.classes_.tolist(),
        'num_classes': num_classes,
        'id_to_label': {i: label for i, label in enumerate(label_encoder.classes_)},
        'label_to_id': {label: i for i, label in enumerate(label_encoder.classes_)}
    }
    with open(artifacts_dir / 'labels.json', 'w') as f:
        json.dump(labels_data, f, indent=2)
    
    logger.info(f"Train: {X_train.shape}, Val: {X_val.shape}, Test: {X_test.shape}")
    logger.info(f"Artifacts saved to {artifacts_dir}")
    
    return (X_train, y_train), (X_val, y_val), (X_test, y_test), label_encoder


def main():
    parser = argparse.ArgumentParser(description="Fixed Sign Language Model Training")
    parser.add_argument('--data_dir', type=str, default='dataset')
    parser.add_argument('--artifacts_dir', type=str, default='artifacts')
    parser.add_argument('--models_dir', type=str, default='models')
    parser.add_argument('--experiments_dir', type=str, default='experiments')
    parser.add_argument('--model_type', type=str, default='simple', choices=['simple', 'advanced'])
    parser.add_argument('--epochs', type=int, default=MAX_EPOCHS)
    parser.add_argument('--batch_size', type=int, default=BATCH_SIZE)
    parser.add_argument('--learning_rate', type=float, default=LEARNING_RATE)
    
    args = parser.parse_args()
    
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    config = {
        'run_timestamp': run_timestamp,
        'data_dir': args.data_dir,
        'artifacts_dir': args.artifacts_dir,
        'models_dir': args.models_dir,
        'experiments_dir': args.experiments_dir,
        'model_type': args.model_type,
        'sequence_length': SEQUENCE_LENGTH,
        'feature_dim': FEATURE_DIM,
        'epochs': args.epochs,
        'batch_size': args.batch_size,
        'learning_rate': args.learning_rate,
        'seed': SEED
    }
    
    try:
        # Load data
        (X_train, y_train), (X_val, y_val), (X_test, y_test), label_encoder = load_data(config['data_dir'])
        num_classes = len(label_encoder.classes_)
        logger.info(f"Training for {num_classes} classes")
        
        # Convert to one-hot encoding
        y_train_ohe = to_categorical(y_train, num_classes)
        y_val_ohe = to_categorical(y_val, num_classes)
        y_test_ohe = to_categorical(y_test, num_classes)
        
        # Compute class weights
        class_weights = compute_class_weight('balanced', classes=np.unique(y_train), y=y_train)
        
        # Initialize trainer
        trainer = FixedSignLanguageTrainer(config)
        
        # Build model
        if config['model_type'] == 'advanced':
            trainer.build_advanced_model(num_classes)
        else:
            trainer.build_simple_model(num_classes)
        
        # Print model summary
        trainer.model.summary()
        
        # Train model
        trainer.train(X_train, y_train_ohe, X_val, y_val_ohe, class_weights)
        
        # Comprehensive evaluation
        results = trainer.evaluate(X_test, y_test_ohe, label_encoder)
        
        # Save artifacts
        trainer.save_model_artifacts(label_encoder)
        
        # Save training results
        run_dir = Path(config['experiments_dir']) / run_timestamp
        with open(run_dir / 'results.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        # Final summary
        print("\n" + "="*80)
        print(" TRAINING COMPLETED SUCCESSFULLY! ")
        print("="*80)
        print(f"[BULLSEYE] Final Test Accuracy: {results['test_accuracy']*100:.2f}%")
        print(f" Top-3 Accuracy: {results['top3_accuracy']*100:.2f}%")
        if results['top5_accuracy'] > 0:
            print(f" Top-5 Accuracy: {results['top5_accuracy']*100:.2f}%")
        print(f" Total Classes: {num_classes}")
        print(f" Model saved to: {trainer.models_dir.absolute()}")
        print(f" Training logs: {run_dir.absolute()}")
        
        if results['test_accuracy'] >= 0.90:
            print("[PARTY_POPPER] SUCCESS: Target accuracy of 90%+ achieved!")
        else:
            print(f" Current accuracy: {results['test_accuracy']*100:.1f}%")
      
        print("="*80)
        
    except Exception as e:
        logger.error(f"Training failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()