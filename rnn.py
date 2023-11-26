from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Embedding, Dropout
from tensorflow.keras.preprocessing.sequence import pad_sequences

# max_sequence_len는 입력 시퀀스의 최대 길이입니다.
# total_words는 데이터셋에 있는 고유 토큰의 수입니다.
# num_classes는 예측해야 하는 클래스의 수입니다.

model = Sequential()
model.add(Embedding(input_dim=total_words, output_dim=128,
          input_length=max_sequence_len-1))  # 임베딩 레이어
# LSTM 레이어, 이후 레이어도 LSTM이면 return_sequences=True
model.add(LSTM(128, return_sequences=True))
model.add(Dropout(0.2))  # 과적합 방지를 위한 드롭아웃 레이어
model.add(LSTM(128))  # 또 다른 LSTM 레이어
model.add(Dense(num_classes, activation='softmax'))  # 분류를 위한 Dense 레이어

model.compile(loss='categorical_crossentropy',
              optimizer='adam', metrics=['accuracy'])

# 모델 요약
model.summary()

# 훈련 데이터와 레이블을 사용하여 모델 훈련
# X_train은 입력 시퀀스, Y_train은 원-핫 인코딩된 정답 레이블
model.fit(X_train, Y_train, epochs=100, verbose=1)

# 모델 저장
model.save('docker_run_model.h5')
