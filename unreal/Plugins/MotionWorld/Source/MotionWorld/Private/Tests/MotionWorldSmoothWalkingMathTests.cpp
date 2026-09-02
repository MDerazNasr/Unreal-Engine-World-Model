#include "Math/SpringMath.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMotionWorldPlanarFacingSpringParityTest,
	"MotionWorld.Nominal.PlanarFacingSpringParity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMotionWorldPlanarFacingSpringParityTest::RunTest(const FString& Parameters)
{
	struct FCase
	{
		float CurrentDegrees;
		float AngularVelocityDegrees;
		float TargetDegrees;
		float SmoothingTimeSeconds;
		float DeltaTimeSeconds;
	};
	const FCase Cases[] = {
		{10.0f, 5.0f, 90.0f, 0.4f, 0.02f},
		{179.0f, 0.0f, -179.0f, 0.4f, 0.02f},
		{-179.0f, 0.0f, 179.0f, 0.4f, 0.02f},
		{-20.0f, -4.0f, 100.0f, 0.2f, 0.01f},
		{0.0f, 0.0f, 0.01f, 0.4f, 0.02f},
	};

	for (int32 Index = 0; Index < UE_ARRAY_COUNT(Cases); ++Index)
	{
		const FCase& TestCase = Cases[Index];
		float AngleRadians = FMath::DegreesToRadians(TestCase.CurrentDegrees);
		float AngleVelocityRadians = FMath::DegreesToRadians(TestCase.AngularVelocityDegrees);
		const float TargetRadians = FMath::DegreesToRadians(TestCase.TargetDegrees);
		FQuat Rotation(FVector::UpVector, AngleRadians);
		FVector RotationVelocityRadians(0.0, 0.0, AngleVelocityRadians);
		const FQuat TargetRotation(FVector::UpVector, TargetRadians);

		SpringMath::CriticalSpringDamperAngle(
			AngleRadians,
			AngleVelocityRadians,
			TargetRadians,
			TestCase.SmoothingTimeSeconds,
			TestCase.DeltaTimeSeconds);
		SpringMath::CriticalSpringDamperQuat(
			Rotation,
			RotationVelocityRadians,
			TargetRotation,
			TestCase.SmoothingTimeSeconds,
			TestCase.DeltaTimeSeconds);

		const FQuat AngleRotation(FVector::UpVector, AngleRadians);
		TestTrue(
			FString::Printf(TEXT("Case %d angle/quaternion orientation parity"), Index),
			AngleRotation.AngularDistance(Rotation) <= 1.0e-5f);
		TestTrue(
			FString::Printf(TEXT("Case %d yaw-rate parity"), Index),
			FMath::IsNearlyEqual(
				AngleVelocityRadians,
				RotationVelocityRadians.Z,
				1.0e-5f));
		TestTrue(
			FString::Printf(TEXT("Case %d no pitch/roll rate"), Index),
			FMath::IsNearlyZero(RotationVelocityRadians.X, 1.0e-6f)
				&& FMath::IsNearlyZero(RotationVelocityRadians.Y, 1.0e-6f));
	}

	(void)Parameters;
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
