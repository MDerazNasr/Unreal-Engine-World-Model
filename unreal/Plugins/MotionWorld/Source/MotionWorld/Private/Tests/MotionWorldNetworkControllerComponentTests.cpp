#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "MotionWorldNetworkControllerComponent.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMotionWorldReactiveTargetContextTest,
	"MotionWorld.Network.ReactiveTargetContext",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMotionWorldReactiveTargetContextTest::RunTest(const FString& Parameters)
{
	using namespace MotionWorld;
	const FVector Target(100.0, -25.0, 0.0);
	const FVector2D TerminalVelocity(5.0, 0.0);

	TestFalse(TEXT("Identical target context is stable"),
		HasReactiveTargetContextChanged(
			true, Target, TerminalVelocity,
			true, Target, TerminalVelocity));
	TestFalse(TEXT("Sub-tolerance float noise is stable"),
		HasReactiveTargetContextChanged(
			true, Target, TerminalVelocity,
			true, Target + FVector(0.001, 0.0, 0.0), TerminalVelocity));
	TestTrue(TEXT("Target presence changes planner context"),
		HasReactiveTargetContextChanged(
			true, Target, TerminalVelocity,
			false, FVector::ZeroVector, FVector2D::ZeroVector));
	TestTrue(TEXT("Target position changes planner context"),
		HasReactiveTargetContextChanged(
			true, Target, TerminalVelocity,
			true, Target + FVector(1.0, 0.0, 0.0), TerminalVelocity));
	TestTrue(TEXT("Terminal velocity changes planner context"),
		HasReactiveTargetContextChanged(
			true, Target, TerminalVelocity,
			true, Target, TerminalVelocity + FVector2D(0.0, 1.0)));

	(void)Parameters;
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
