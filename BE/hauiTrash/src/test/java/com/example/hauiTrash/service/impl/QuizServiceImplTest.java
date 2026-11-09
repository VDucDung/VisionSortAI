package com.example.hauiTrash.service.impl;

import com.example.hauiTrash.dto.QuizResultDTO;
import com.example.hauiTrash.dto.QuizStartDTO;
import com.example.hauiTrash.dto.QuizSubmitDTO;
import com.example.hauiTrash.dto.QuestionDTO;
import com.example.hauiTrash.entity.Question;
import com.example.hauiTrash.entity.Quiz;
import com.example.hauiTrash.entity.QuizAttempt;
import com.example.hauiTrash.entity.UserQuiz;
import com.example.hauiTrash.repository.QuestionRepository;
import com.example.hauiTrash.repository.QuizAttemptRepository;
import com.example.hauiTrash.repository.QuizRepository;
import com.example.hauiTrash.repository.UserQuizRepository;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class QuizServiceImplTest {

    private static final long QUIZ_ID = 9L;
    private static final long STORY_ID = 44L;
    private static final int ACCOUNT_ID = 7;

    @Mock
    private QuizRepository quizRepository;

    @Mock
    private QuestionRepository questionRepository;

    @Mock
    private UserQuizRepository userQuizRepository;

    @Mock
    private QuizAttemptRepository quizAttemptRepository;

    private final ObjectMapper objectMapper = new ObjectMapper();
    private QuizServiceImpl quizService;

    @BeforeEach
    void setUp() {
        quizService = new QuizServiceImpl(
                quizRepository,
                questionRepository,
                userQuizRepository,
                quizAttemptRepository,
                objectMapper);
    }

    @Test
    void getQuizByStoryIdUsesDefaultPassingScoreAndTotalsQuestionPoints() {
        Quiz quiz = quiz(null);
        List<Question> questions = List.of(question(1L, "A", 4), question(2L, "B", 6));
        when(quizRepository.findByStoryId(STORY_ID)).thenReturn(Optional.of(quiz));
        when(questionRepository.findByQuizId(QUIZ_ID)).thenReturn(questions);

        var result = quizService.getQuizByStoryId(STORY_ID);

        assertEquals(50, result.getPassingScore());
        assertEquals(10, result.getTotalPoints());
        assertEquals(2, result.getQuestions().size());
    }

    @Test
    void startQuizStopsWhenAccountHasCompletedRequiredQuizCount() {
        when(userQuizRepository.countPassedQuizzesByUserId((long) ACCOUNT_ID)).thenReturn(5L);

        assertThrows(RuntimeException.class, () -> quizService.startQuiz(ACCOUNT_ID, STORY_ID));

        verifyNoInteractions(quizRepository, questionRepository, quizAttemptRepository);
    }

    @Test
    void startQuizDeletesPreviousIncompleteAttemptAndPersistsShuffledQuestions() throws Exception {
        Quiz quiz = quiz(60);
        List<Question> questions = List.of(
                question(1L, "A", 4),
                question(2L, "B", 6));
        QuizAttempt previousAttempt = QuizAttempt.builder().id(15L).build();
        when(userQuizRepository.countPassedQuizzesByUserId((long) ACCOUNT_ID)).thenReturn(0L);
        when(quizRepository.findByStoryId(STORY_ID)).thenReturn(Optional.of(quiz));
        when(userQuizRepository.existsByUserIdAndQuizIdAndIsPassedTrue((long) ACCOUNT_ID, QUIZ_ID))
                .thenReturn(false);
        when(quizAttemptRepository.findByUserIdAndQuizIdAndIsCompletedFalse((long) ACCOUNT_ID, QUIZ_ID))
                .thenReturn(Optional.of(previousAttempt));
        when(questionRepository.findByQuizId(QUIZ_ID)).thenReturn(questions);
        when(quizAttemptRepository.save(any(QuizAttempt.class))).thenAnswer(invocation -> {
            QuizAttempt attempt = invocation.getArgument(0);
            attempt.setId(17L);
            return attempt;
        });

        QuizStartDTO result = quizService.startQuiz(ACCOUNT_ID, STORY_ID);

        assertEquals("17", result.getAttemptToken());
        assertEquals(10, result.getQuiz().getTotalPoints());
        assertEquals(2, result.getQuiz().getQuestions().size());
        for (QuestionDTO question : result.getQuiz().getQuestions()) {
            assertEquals(Set.of("A", "B", "C", "D"), Set.of(
                    question.getOptionA(), question.getOptionB(), question.getOptionC(), question.getOptionD()));
        }
        verify(quizAttemptRepository).delete(previousAttempt);
        ArgumentCaptor<QuizAttempt> attemptCaptor = ArgumentCaptor.forClass(QuizAttempt.class);
        verify(quizAttemptRepository).save(attemptCaptor.capture());
        assertFalse(attemptCaptor.getValue().getIsCompleted());
        assertTrue(objectMapper.readValue(attemptCaptor.getValue().getQuestionOrder(),
                new TypeReference<List<Long>>() {}).containsAll(List.of(1L, 2L)));
    }

    @Test
    void startQuizRejectsQuizWithoutQuestions() {
        when(userQuizRepository.countPassedQuizzesByUserId((long) ACCOUNT_ID)).thenReturn(0L);
        when(quizRepository.findByStoryId(STORY_ID)).thenReturn(Optional.of(quiz(50)));
        when(userQuizRepository.existsByUserIdAndQuizIdAndIsPassedTrue((long) ACCOUNT_ID, QUIZ_ID))
                .thenReturn(false);
        when(quizAttemptRepository.findByUserIdAndQuizIdAndIsCompletedFalse((long) ACCOUNT_ID, QUIZ_ID))
                .thenReturn(Optional.empty());
        when(questionRepository.findByQuizId(QUIZ_ID)).thenReturn(List.of());

        assertThrows(RuntimeException.class, () -> quizService.startQuiz(ACCOUNT_ID, STORY_ID));

        verify(quizAttemptRepository, never()).save(any(QuizAttempt.class));
    }

    @Test
    void submitQuizMapsShuffledAnswersAndPersistsPassingResult() throws Exception {
        QuizAttempt attempt = attempt(ACCOUNT_ID, false);
        Question first = question(1L, "C", 10);
        Question second = question(2L, "D", 10);
        QuizSubmitDTO submitData = submission(Map.of(1L, "B", 2L, "A"));
        when(quizAttemptRepository.findById(17L)).thenReturn(Optional.of(attempt));
        when(questionRepository.findByQuizId(QUIZ_ID)).thenReturn(List.of(first, second));
        when(quizRepository.findById(QUIZ_ID)).thenReturn(Optional.of(quiz(50)));

        QuizResultDTO result = quizService.submitQuiz(ACCOUNT_ID, submitData);

        assertEquals(10, result.getScore());
        assertEquals(20, result.getTotalPoints());
        assertEquals(50.0, result.getPercentage(), 0.001);
        assertTrue(result.getIsPassed());
        assertEquals(true, result.getCorrectAnswers().get(1L));
        assertEquals(false, result.getCorrectAnswers().get(2L));
        assertTrue(attempt.getIsCompleted());

        ArgumentCaptor<UserQuiz> userQuizCaptor = ArgumentCaptor.forClass(UserQuiz.class);
        verify(userQuizRepository).save(userQuizCaptor.capture());
        assertEquals(10, userQuizCaptor.getValue().getScore());
        assertTrue(userQuizCaptor.getValue().getIsPassed());
    }

    @Test
    void submitQuizRejectsAttemptOwnedByAnotherAccount() throws Exception {
        when(quizAttemptRepository.findById(17L)).thenReturn(Optional.of(attempt(8, false)));

        assertThrows(RuntimeException.class,
                () -> quizService.submitQuiz(ACCOUNT_ID, submission(Map.of(1L, "A"))));

        verify(quizAttemptRepository, never()).save(any(QuizAttempt.class));
        verifyNoInteractions(questionRepository, quizRepository, userQuizRepository);
    }

    private Quiz quiz(Integer passingScore) {
        return Quiz.builder()
                .id(QUIZ_ID)
                .storyId(STORY_ID)
                .title("Recycling quiz")
                .timeLimitMinutes(15)
                .passingScore(passingScore)
                .build();
    }

    private Question question(Long id, String correctAnswer, int points) {
        return Question.builder()
                .id(id)
                .quizId(QUIZ_ID)
                .questionText("Select the correct option")
                .optionA("A")
                .optionB("B")
                .optionC("C")
                .optionD("D")
                .correctAnswer(correctAnswer)
                .points(points)
                .explanation("Answer explanation")
                .build();
    }

    private QuizAttempt attempt(int accountId, boolean completed) throws Exception {
        Map<Long, Map<String, String>> optionsMapping = Map.of(
                1L, Map.of("A", "A", "B", "C", "C", "B", "D", "D"),
                2L, Map.of("A", "B", "B", "A", "C", "C", "D", "D"));
        return QuizAttempt.builder()
                .id(17L)
                .userId((long) accountId)
                .quizId(QUIZ_ID)
                .optionsMapping(objectMapper.writeValueAsString(optionsMapping))
                .isCompleted(completed)
                .build();
    }

    private QuizSubmitDTO submission(Map<Long, String> answers) {
        QuizSubmitDTO submitData = new QuizSubmitDTO();
        submitData.setAttemptToken("17");
        submitData.setAnswers(answers);
        return submitData;
    }
}