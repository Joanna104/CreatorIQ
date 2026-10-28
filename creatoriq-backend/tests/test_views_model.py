from predict import predict_views

sample = {
    "duration": 30,
    "word_count": 80,
    "emoji_count": 2,
    "question_count": 1,
    "hashtag_count": 4,
    "speaking_rate": 160,
    "prior_follower_count": 1000,
    "prior_following_count": 300,
    "prior_total_favorited": 5000,
    "prior_video_count": 50,
    "history_age_days": 180,
    "topic": "skincare",
    "desc_language": "en"
}

prediction = predict_views(sample)
print("Predicted Day-7 views:", float(prediction[0]))